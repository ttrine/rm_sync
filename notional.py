from notion_client import Client

from notion.client import NotionClient as UnofficialClient
from notion.block import BulletedListBlock, PageBlock


class Notion:
    """ Mediates interaction with the Notion APIs.

    We use the official Notion API whenever possible, but the unofficial one is *much* more powerful. """
    def __init__(self, official_token, unofficial_token, root):
        self.client = Client(auth=official_token)
        self.other_client = UnofficialClient(token_v2=unofficial_token)
        self.ROOT = root

    @staticmethod
    def header(text):
        """ JSON representation of a Notion block containing H2-sized text. """
        return {'object': 'block',
                'type': 'heading_2',
                'heading_2': {'text': [{
                    'text': {'content': text}
                }]}}

    @staticmethod
    def file(name, url):
        """ JSON representation of a Notion block containing a bulleted link to a URL. """
        return {'object': 'block',
                'type': 'bulleted_list_item',
                'bulleted_list_item': {'text': [{
                    'type': 'text',
                    'text': {'content': name,
                             'link': {'url': url}}
                }]}}

    @staticmethod
    def sub_folder(parent_id, name):
        """ JSON request that adds a sub-page. """
        return {
            'parent': {
                "page_id": parent_id
            },
            'properties': {"title": {"title": [{"text": {
                "content": name
            }}]}}
        }

    def append_header(self, parent_id, text):
        """ Append a header block to a given Notion page. """
        self.client.blocks.children.append(parent_id, children=[self.header(text)])

    def append_files(self, parent_id, drive_files):
        """ Append a list of bulleted links to a given Notion page. """
        self.client.blocks.children.append(parent_id, children=[
            self.file(file['name'], file['url']) for file in drive_files.values()
        ])

    def append_sub_folder(self, parent_id, name):
        """ Append a sub-folder as a sub-page of a given Notion page. """
        return self.client.pages.create(**self.sub_folder(parent_id, name))

    def add_sub_folder(self, parent_id, name):
        """ Add a sub-folder as a sub-page of a Notion page with a given ID using the unofficial Notion API.

        The difference from append_sub_folder is that this function re-sorts the folder list alphabetically. """

        block = self.other_client.get_block(parent_id)

        # First add the link to the end of the page
        block.children.add_new(PageBlock, title=name)

        # Then re-arrange the folder list to include the new folder in alphabetical order
        folders_header_index = [i for i, child in enumerate(block.children) if child.title == 'Folders'][0]
        folders = block.children[folders_header_index + 1:]
        folders = sorted(folders, key=lambda folder: folder.title.lower())

        # Finally re-assemble the entire list of children and set that as the block's contents
        new_id_list = [child.id for child in block.children[:folders_header_index + 1]]
        new_id_list.extend([child.id for child in folders])

        block.set('content', new_id_list)

    def get_file_ids(self, parent_id):
        """ Return a list of IDs for all files listed on a given Notion page. """
        children = self.client.blocks.children.list(parent_id)['results']
        return [block['id'] for block in children
                if block['type'] == 'bulleted_list_item']

    def delete(self, id_):
        """ Delete a block with a given ID using the unofficial Notion API. """
        self.other_client.get_block(id_).remove()

    def rename_file(self, id_, text):
        """ Rename a file link block with a given ID using the unofficial Notion API. """
        block = self.other_client.get_block(id_)
        _, url = tuple(block.title.replace('[', '').replace(')', '').split(']('))
        block.title = f"[{text}]({url})"

    def relink_file(self, id_, url):
        """ Change the URL of a file link block with a given ID using the unofficial Notion API. """
        block = self.other_client.get_block(id_)
        text, _ = tuple(block.title.replace('[', '').replace(')', '').split(']('))
        block.title = f"[{text}]({url})"

    def add_file(self, id_, name, url):
        """ Add a bulleted file link in alphabetical order to a Notion page using the unofficial Notion API. """
        block = self.other_client.get_block(id_)

        # First add the link to the end of the page
        block.children.add_new(BulletedListBlock, title=f"[{name}]({url})")

        # Then re-arrange the file list to include the new file in alphabetical order
        folders_header_index = [i for i, child in enumerate(block.children) if child.title == 'Folders'][0]
        files = block.children[1:folders_header_index]
        files.append(block.children[-1])
        files = sorted(files, key=lambda file: file.title.lower())

        # Finally re-assemble the entire list of children and set that as the block's contents
        new_id_list = [block.children[0].id]
        new_id_list.extend([file.id for file in files])

        new_id_list.extend([child.id for child in block.children[folders_header_index:-1]])

        block.set('content', new_id_list)

    def rename_sub_folder(self, id_, name):
        """ Rename a Notion folder with a given ID using the unofficial Notion API. """
        self.other_client.get_block(id_).title = name

