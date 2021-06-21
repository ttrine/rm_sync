from rm import RM
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


async def process_file(rm_file, drive_id):
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


async def process_files(folder, rm_files):
    """ Process all the files in a folder. """
    for rm_file in rm_files:
        drive_file = await process_file(rm_file, folder.drive.id_)

        # If the upload went smoothly, record it
        if drive_file:
            folder.rm.add_file(rm_file.id, rm_file.version)
            folder.drive.add_file(rm_file.id, dict(id=drive_file['id'],
                                                   name=rm_file.name,
                                                   url=drive_file['embedLink']))

    # Add the 'Files' header if there is at least one file
    if len(folder.drive.files) > 0:
        notion.append_header(folder.notion.id_, "Files")

    # Then, add the file links to Notion
    notion.append_files(folder.notion.id_, folder.drive.files)

    # Finally, record the resulting notion ID of each file link
    notion_file_ids = notion.get_file_ids(folder.notion.id_)
    for rm_file, notion_file_id in zip(rm_files, notion_file_ids):
        folder.notion.add_file(rm_file.id, notion_file_id)


async def process_sub_folder(folder, rm_sub_folder):
    logger.info(f"Mirroring folder {rm_sub_folder.name}")

    drive_sub_folder = drive.create_folder(folder.drive.id_, rm_sub_folder.name)
    notion_sub_folder = notion.append_sub_folder(folder.notion.id_, rm_sub_folder.name)

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

    await mirror(sub_folder)

    logger.info(f"Finished processing folder {sub_folder.name}")


async def process_sub_folders(folder, rm_sub_folders):
    # Add the 'Folders' header, but only if there's at least one folder
    if len(rm_sub_folders) > 0:
        notion.append_header(folder.notion.id_, "Folders")

    for rm_sub_folder in rm_sub_folders:
        await process_sub_folder(folder, rm_sub_folder)


async def mirror(folder):
    """ Recursively mirror the contents of a Remarkable folder to Drive and Notion. """
    rm_files, rm_sub_folders = await rm.get_contents(folder.rm.id_)

    await process_files(folder, rm_files)
    await process_sub_folders(folder, rm_sub_folders)

    folder.save()


if __name__ == '__main__':
    root_folder = Folder('root',
                         rm=dict(id_=rm.ROOT),
                         drive=dict(id_=drive.ROOT),
                         notion=dict(id_=notion.ROOT))

    # Run the mirror recursion
    trio.run(mirror, root_folder)

    logger.info("Mirroring complete")
