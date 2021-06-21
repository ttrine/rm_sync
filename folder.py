""" Infrastructure for keeping track of data across RM, Drive, and Notion. """
import json


class FolderData:
    def __init__(self, id_, files=None, sub_folders=None):
        self.id_ = id_
        self.files = files if files else dict()
        self.sub_folders = sub_folders if sub_folders else dict()

    def add_file(self, key, value):
        self.files[key] = value

    def add_sub_folder(self, key, value):
        self.sub_folders[key] = value


class Folder:
    """ Groups RM, Drive, and Notion data together into a single object. """
    def __init__(self, name, **kwargs):
        self.name = name

        # The Folder's identity is contingent on its RM identity
        self.id_ = kwargs['rm']['id_']

        self.rm = FolderData(**kwargs['rm'])
        self.drive = FolderData(**kwargs['drive'])
        self.notion = FolderData(**kwargs['notion'])

    def save(self):
        """ Serialize the contents of this folder to a JSON file. """
        with open(f"folder_state/{self.id_}.json", 'w') as file:
            json.dump(self, file, default=vars)

    @classmethod
    def maybe_load(cls, id_):
        """ Try to construct a Folder instance from a JSON file.

        If the file doesn't exist, return empty-handed. """
        try:
            with open(f"folder_state/{id_}.json", 'r') as file:
                folder_dict = json.load(file)

            return cls(**folder_dict)

        except FileNotFoundError as e:
            return
