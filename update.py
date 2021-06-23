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


async def convert_to_pdf(rm_file):
    """ Convert a raw RM file to a PDF. """
    logger.info(f"Converting {await rm_file.type()} {rm_file.name}. id_:{rm_file.id}")
    try:
        return await rm_file.annotated()
    except TypeError as e:
        logger.error(f"Could not convert {rm_file.name} to PDF, likely due to missing size info in the original PDF.")
        logger.error(f"Error message:{e}")
        return
    except Exception as e:
        logger.error(f"Could not convert {rm_file.name} to PDF for some unknown reason.")
        logger.error(f"Error message: {e}")
        return


async def create_file(rm_file, drive_id):
    """ Convert an new RM file to PDF and upload it to Drive. """
    pdf = await convert_to_pdf(rm_file)
    if not pdf:
        return
    try:
        logger.debug("Uploading to drive")
        return drive.upload_pdf(drive_id, rm_file.name, pdf)
    except Exception as e:
        logger.error(f"Could not upload {rm_file.name} to drive.")
        logger.error(f"Error message: {e}")
        return


async def modify_file(folder, rm_file):
    """ Rename and re-upload a modified RM file to Drive and Notion. """
    pdf = await convert_to_pdf(rm_file)
    try:
        logger.debug("Renaming on Drive and Notion")
        drive.rename(folder.drive.files[rm_file.id]['id'], rm_file.name)
        notion.rename_file(folder.notion.files[rm_file.id], rm_file.name)

        logger.debug("Uploading to drive")
        drive.replace_pdf(folder.drive.files[rm_file.id]['id'], pdf)

        return True

    except Exception as e:
        logger.error(f"Could not update {rm_file.name}.")
        logger.error(f"Error message: {e}")
        return


async def delete_file(folder, rm_file):
    """ Delete a removed RM file from Drive and Notion. """
    try:
        logger.debug("Deleting Drive file")
        drive.delete(folder.drive.files[rm_file.id]['id'])
        logger.debug("Deleting Notion file")
        notion.delete(folder.notion.files[rm_file.id])
        return True
    except Exception as e:
        logger.error(f"Could not delete {rm_file.name}.")
        logger.error(f"Error message: {e}")


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

            notion_file = notion.add_file(folder.notion.id_, rm_file.name, drive_file['embedLink'])
            folder.notion.add_file(rm_file.id, notion_file.id)

    for rm_file in file_updates.modified:
        success = await modify_file(folder, rm_file)

        # If the upload went smoothly, update the Folder data
        if success:
            folder.rm.add_file(rm_file.id, rm_file.version)
            folder.drive.files[rm_file.id]['name'] = rm_file.name

    for rm_file in file_updates.deleted:
        success = await delete_file(folder, rm_file)

        # If the upload went smoothly, delete the associated Folder data
        if success:
            del folder.rm.files[rm_file.id]
            del folder.drive.files[rm_file.id]
            del folder.notion.files[rm_file.id]


async def create_sub_folder(folder, rm_sub_folder):
    logger.info(f"Creating sub-folder {rm_sub_folder.name}")

    try:
        drive_sub_folder = drive.create_folder(folder.drive.id_, rm_sub_folder.name)
        notion_sub_folder = notion.add_sub_folder(folder.notion.id_, rm_sub_folder.name)
        return drive_sub_folder, notion_sub_folder
    except Exception as e:
        logger.error(f"Could not upload {rm_sub_folder.name}.")
        logger.error(f"Error message: {e}")
        return


async def modify_sub_folder(folder, rm_sub_folder):
    logger.info(f"Updating modified folder {rm_sub_folder.name}")

    try:
        drive.rename(folder.drive.sub_folders[rm_sub_folder.id]['id'], rm_sub_folder.name)
        notion.rename_sub_folder(folder.notion.sub_folders[rm_sub_folder.id], rm_sub_folder.name)
        return True
    except Exception as e:
        logger.error(f"Could not update {rm_sub_folder.name}.")
        logger.error(f"Error message: {e}")
        return


async def delete_sub_folder(folder, rm_sub_folder):
    logger.info(f"Deleting folder {rm_sub_folder.name}")

    try:
        logger.debug("Renaming on Drive and Notion")
        drive.delete(folder.drive.sub_folders[rm_sub_folder.id]['id'])
        notion.delete(folder.notion.sub_folders[rm_sub_folder.id])
        return True
    except Exception as e:
        logger.error(f"Could not delete {rm_sub_folder.name}.")
        logger.error(f"Error message: {e}")
        return


async def process_sub_folders(folder, folder_updates):
    for new_sub_folder in folder_updates.created:
        result = await create_sub_folder(folder, new_sub_folder)

        # If the upload went smoothly, record it in the Folder
        if result:
            drive_sub_folder, notion_sub_folder = result
            folder.rm.add_sub_folder(new_sub_folder.id, new_sub_folder.version)
            folder.drive.add_sub_folder(new_sub_folder.id, dict(id=drive_sub_folder['id'],
                                                                name=new_sub_folder.name,
                                                                url=drive_sub_folder['embedLink']))
            folder.notion.add_sub_folder(new_sub_folder.id, notion_sub_folder.id)

    for modified_sub_folder in folder_updates.modified:
        success = await modify_sub_folder(folder, modified_sub_folder)

        # If the upload went smoothly, update the Folder data that has changed
        if success:
            folder.rm.add_sub_folder(modified_sub_folder.id, modified_sub_folder.version)
            folder.drive.sub_folders[modified_sub_folder.id]['name'] = modified_sub_folder.name

    for deleted_sub_folder in folder_updates.deleted:
        success = await delete_sub_folder(folder, deleted_sub_folder)

        # If the upload went smoothly, delete the associated Folder data
        if success:
            del folder.rm.sub_folders[deleted_sub_folder.id]
            del folder.drive.sub_folders[deleted_sub_folder.id]
            del folder.notion.sub_folders[deleted_sub_folder.id]

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

    if len(file_updates.created) > 0:
        logger.info(f"New files: {file_updates.created}")
    if len(file_updates.modified) > 0:
        logger.info(f"Modified files: {file_updates.modified}")
    if len(file_updates.deleted) > 0:
        logger.info(f"Deleted files: {file_updates.deleted}")

    if len(folder_updates.created) > 0:
        logger.info(f"New folders: {folder_updates.created}")
    if len(folder_updates.modified) > 0:
        logger.info(f"Modified folders: {folder_updates.modified}")
    if len(folder_updates.deleted) > 0:
        logger.info(f"Deleted folders: {folder_updates.deleted}")

    await process_files(folder, file_updates)
    await process_sub_folders(folder, folder_updates)

    # If something has changed, update the folder contents on disk
    if file_updates.change or folder_updates.change:
        folder.save()


if __name__ == '__main__':
    try:
        root_folder = Folder('root',
                             rm=dict(id_=rm.ROOT),
                             drive=dict(id_=drive.ROOT),
                             notion=dict(id_=notion.ROOT))

        # Run the mirror_updates recursion
        trio.run(mirror_updates, root_folder)
    except Exception as e:
        logger.error("An unexpected error occurred while executing the update script.")
        logger.error(f"Error message: {e}")

    logger.info("Update complete")
