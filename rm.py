import rmcl
from rmcl import Item, Document


class RM:
    """ Mediates interaction with the Remarkable API. """
    ROOT = ''

    # RM has a one-time device authentication which we already did on this machine
    client = rmcl.api.get_client_s()

    @staticmethod
    async def get_contents(id_):
        """ Return sorted lists of files and sub-folders in the specified Remarkable directory. """
        folder_ob = await Item.get_by_id(id_)
        children = set(folder_ob.children)

        files = {c for c in children if isinstance(c, Document)}
        folders = {c for c in children - files if c.name != '.trash'}

        files = sorted(files, key=lambda document: document.name)
        folders = sorted(folders, key=lambda document: document.name)

        return files, folders

    async def get_updates(self, id_, old_files, old_sub_folders):
        """ Figure out what's changed since the last sync. """

        # This updates the by_id dict for *all* RM items, so only needs to be called once at the root
        if id_ == self.ROOT:
            await self.client.update_items()

        new_files, new_sub_folders = await self.get_contents(id_)

        file_updates = Updates(new_files, old_files, self.client.by_id)
        folder_updates = Updates(new_sub_folders, old_sub_folders, self.client.by_id)

        return file_updates, folder_updates


class Updates:
    """ Determine which items have changed and how in a given RM directory since the last run. """
    def __init__(self, new_items, old_items=None, by_id=None):
        self.by_id = by_id
        self.old_items = old_items
        self.new_items = new_items

        if by_id:  # This is a true update record
            self.created = [item for item in new_items if self.created_q(item)]
            self.modified = [by_id[item] for item, version in old_items.items() if self.modified_q(item, version)]
            self.deleted = [item for item in new_items if self.deleted_q(item)]
        else:  # This is a wrapper around a bunch of new items
            self.created = new_items
            self.modified = []
            self.deleted = []

    def created_q(self, new_item):
        """ Returns True if the item is new and False otherwise. """
        return False if new_item.id in self.old_items else True

    def modified_q(self, old_item, old_version):
        """ Returns True if the item has been modified and False otherwise. """
        if old_item not in self.by_id:
            return False  # If this is possible, it would count as deleted
        elif self.by_id[old_item].version == old_version:
            return False
        else:
            return True

    def deleted_q(self, new_item):
        """ Returns True if the item has been deleted and False otherwise. """

        # Normally the ID should show up as a child of the trash folder, but check just in case
        if new_item.id not in self.by_id:
            return True
        elif self.by_id[new_item.id].parent == 'trash':
            return True
        else:
            return False
