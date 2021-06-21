from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive


class Drive:
    """ Mediates interaction with the Google Drive API. """
    def __init__(self):
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        self.client = GoogleDrive(gauth)
        self.ROOT = self.client.ListFile({
            'q': "'root' in parents and title = 'remarkable' and trashed=false"
        }).GetList()[0]['id']

    def upload_pdf(self, parent_id, name, pdf):
        """ Upload an in-memory PDF to drive. """
        metadata = {
            'title': name,
            "parents": [{'id': parent_id}]
        }

        file = self.client.CreateFile(metadata)

        file.content = pdf
        file["mimeType"] = 'application/pdf'

        file.Upload()

        return file

    def create_folder(self, parent_id, name):
        """ Add a folder to drive under the specified parent_id folder. """
        folder = self.client.CreateFile({'title': name,
                                         "parents": [{"kind": "drive#fileLink", "id": parent_id}],
                                         "mimeType": "application/vnd.google-apps.folder"})
        folder.Upload()

        return folder

    def delete(self, id_):
        """ Delete an existing drive file or folder with a given id. """
        self.client.CreateFile({'id': id_}).Trash()

    def rename(self, id_, name):
        """ Rename an existing drive file or folder with a given id without changing its contents. """
        item = self.client.CreateFile({'id': id_})
        item.FetchMetadata()
        item['title'] = name
        item.Upload()

    def replace_pdf(self, id_, pdf):
        """ Replace the content of an existing drive PDF with a given id. """
        file = self.client.CreateFile({'id': id_})
        file.content = pdf
        file.Upload()
