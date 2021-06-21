from rm import RM, Updates
from drive import Drive
from notional import Notion

from folder import Folder

from log import set_up_logger

import os
import trio

logger = set_up_logger(__name__)

# Initialize and authenticate the APIs
rm = RM()
drive = Drive()
notion = Notion(os.environ["OFFICIAL_NOTION_TOKEN"],
                os.environ["UNOFFICIAL_NOTION_TOKEN"],
                os.environ["NOTION_ROOT"])


async def create_file(rm_file, drive_id):
    """ Convert a raw RM file to a PDF, upload it to Drive, and return the upload URL. """
    logger.info(f"Processing {await rm_file.type()} {rm_file.name}. id_:{rm_file.id}")
    logger.info("\tConverting to PDF")
    try:
        pdf = await rm_file.annotated()
    except TypeError as e:
        logger.error(f"\tCould not convert {rm_file.name} to PDF, "
                     f"likely due to missing size info in the original PDF:\n\t{e}")
        return
    except Exception as e:
        logger.error(f"\tCould not convert {rm_file.name} to PDF for some unknown reason:\n\t{e}")
        return

    try:
        logger.info("\tUploading to drive")
        return drive.upload_pdf(drive_id, rm_file.name, pdf)
    except Exception as e:
        logger.error(f"\tCould not upload {rm_file.name} to drive:\n\t{e}")
        return


async def modify_file(folder, rm_file):
    """ Rename and re-upload a modified RM file to Drive and Notion. """
    logger.info(f"Updating {await rm_file.type()} {rm_file.name}. id_:{rm_file.id}")
    try:
        pdf = await rm_file.annotated()
    except TypeError as e:
        logger.error(f"\tCould not convert {rm_file.name} to PDF, "
                     f"likely due to missing size info in the original PDF:\n\t{e}")
        return
    except Exception as e:
        logger.error(f"\tCould not convert {rm_file.name} to PDF for some unknown reason:\n\t{e}")
        return

    try:
        if folder.name != rm_file.name:
            logger.info("\tFile name has changed, renaming on Drive and Notion")
        drive.rename(folder.drive.files[rm_file.id], rm_file.name)
        notion.rename_file(folder.notion.files[rm_file.id], rm_file.name)
        logger.info("\tUploading to drive")
        return drive.replace_pdf(folder.drive.files[rm_file.id], pdf)
    except Exception as e:
        logger.error(f"\tCould not update {rm_file.name} in drive:\n\t{e}")
        return


async def delete_file(folder, rm_file):
    """ Delete a removed RM file from Drive and Notion. """
    drive.delete(folder.drive.files[rm_file.id])
    notion.delete(folder.notion.files[rm_file.id])

    del folder.drive.files[rm_file.id]
    del folder.notion.files[rm_file.id]


async def process_files(folder, file_updates):
    """ Process all the file updates in a folder. """
    for rm_file in file_updates.created:
        drive_file = await create_file(rm_file, folder.drive.id_)

        # If the upload went smoothly, record it in the Folder and add the file link to Notion
        if drive_file:
            folder.rm.add_file(rm_file.id, rm_file.version)
            folder.drive.add_file(rm_file.id, dict(id=drive_file['id'],
                                                   name=rm_file.name,
                                                   url=drive_file['embedLink']))
            notion.add_file(folder.notion.id_, rm_file.name, drive_file['embedLink'])

    for rm_file in file_updates.modified:
        await modify_file(folder, rm_file)

    for rm_file in file_updates.deleted:
        await delete_file(folder, rm_file)


async def create_sub_folder(folder, rm_sub_folder):
    logger.info(f"Creating sub-folder {rm_sub_folder.name}")

    drive_sub_folder = drive.create_folder(folder.drive.id_, rm_sub_folder.name)
    notion_sub_folder = notion.add_sub_folder(folder.notion.id_, folder.name)

    # Record the sub-folder data
    folder.rm.add_sub_folder(rm_sub_folder.id, rm_sub_folder.version)
    folder.drive.add_sub_folder(rm_sub_folder.id, dict(id=drive_sub_folder['id'],
                                                       name=rm_sub_folder.name,
                                                       url=drive_sub_folder['embedLink']))
    folder.notion.add_sub_folder(rm_sub_folder.id, notion_sub_folder['id'])

    sub_folder = Folder(rm_sub_folder.name,
                        rm=dict(id_=rm_sub_folder.id),
                        drive=dict(id_=drive_sub_folder['id']),
                        notion=dict(id_=notion_sub_folder['id']))

    return sub_folder


async def modify_sub_folder(folder, rm_sub_folder):
    logger.info(f"Updating modified folder {rm_sub_folder.name}")

    # Update Drive and Notion
    drive.rename(folder.drive.sub_folders[rm_sub_folder.id], rm_sub_folder.name)
    notion.rename_sub_folder(folder.notion.sub_folders[rm_sub_folder.id], rm_sub_folder.name)

    # Update sub-folder data
    folder.rm.add_sub_folder(rm_sub_folder.id, rm_sub_folder.version)
    folder.drive.sub_folders[rm_sub_folder.id]['name'] = rm_sub_folder.name

    sub_folder = Folder(rm_sub_folder.name,
                        id_=rm_sub_folder.id,
                        rm=dict(id_=rm_sub_folder.id),
                        drive=dict(id_=folder.drive.sub_folders[rm_sub_folder.id]),
                        notion=dict(id_=folder.notion.sub_folders[rm_sub_folder.id]))

    return sub_folder


async def delete_sub_folder(folder, rm_sub_folder):
    logger.info(f"Deleting folder {rm_sub_folder.name}")

    drive.delete(folder.drive.sub_folders[rm_sub_folder.id])
    notion.delete(folder.notion.sub_folders[rm_sub_folder.id])

    del folder.drive.sub_folders[rm_sub_folder.id]
    del folder.notion.sub_folders[rm_sub_folder.id]


async def process_sub_folders(folder, folder_updates):
    for new_sub_folder in folder_updates.created:
        await create_sub_folder(folder, new_sub_folder)

    for modified_sub_folder in folder_updates.modified:
        await modify_sub_folder(folder, modified_sub_folder)

    for deleted_sub_folder in folder_updates.deleted:
        await delete_sub_folder(folder, deleted_sub_folder)

    # Process sub-folder contents *after* making all the updates at this level
    for rm_id_ in folder.rm.sub_folders.keys():
        await mirror_updates(Folder(folder.drive.sub_folders[rm_id_]['name'],
                                    rm=dict(id_=rm_id_),
                                    drive=dict(id_=folder.drive.sub_folders[rm_id_]['id']),
                                    notion=dict(id_=folder.notion.sub_folders[rm_id_])))


async def mirror_updates(folder):
    """ Recursively mirror updates in a Remarkable folder to Drive and Notion. """
    old_folder = Folder.maybe_load(folder.id_)

    if old_folder:
        # This is the folder instance we want, if it exists
        folder = old_folder
        file_updates, folder_updates = await rm.get_updates(folder.id_,
                                                            folder.rm.files,
                                                            folder.rm.sub_folders)
    else:
        # Keep the Folder instance that was passed in and treat everything as new
        files, sub_folders = await rm.get_contents(folder.id_)
        file_updates = Updates(files)
        folder_updates = Updates(sub_folders)

    logger.info(f"Found {len(file_updates.created)} new files, "
                f"{len(file_updates.modified)} modified files, "
                f"and {len(file_updates.deleted)} deleted files")

    if len(file_updates.created) > 0:
        logger.info(f"New files: {file_updates.created}")
    if len(file_updates.modified) > 0:
        logger.info(f"Modified files: {file_updates.modified}")
    if len(file_updates.deleted) > 0:
        logger.info(f"Deleted files: {file_updates.deleted}")

    logger.info(f"Found {len(folder_updates.created)} new folders, "
                f"{len(folder_updates.modified)} modified folders, "
                f"and {len(folder_updates.deleted)} deleted folders")

    if len(folder_updates.created) > 0:
        logger.info(f"New folders: {folder_updates.created}")
    if len(folder_updates.modified) > 0:
        logger.info(f"Modified folders: {folder_updates.modified}")
    if len(folder_updates.deleted) > 0:
        logger.info(f"Deleted folders: {folder_updates.deleted}")

    await process_files(folder, file_updates)
    await process_sub_folders(folder, folder_updates)

if __name__ == '__main__':
    root_folder = Folder('root',
                         rm=dict(id_=rm.ROOT),
                         drive=dict(id_=drive.ROOT),
                         notion=dict(id_=notion.ROOT))

    # Run the mirror_updates recursion
    trio.run(mirror_updates, root_folder)

    logger.info("Update complete")
