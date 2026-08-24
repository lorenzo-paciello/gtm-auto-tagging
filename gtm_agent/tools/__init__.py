"""Ferramentas (function tools) disponibilizadas aos agentes."""

from .docs_tools import list_docs
from .docs_tools import read_doc
from .docs_tools import save_custom_doc
from .docs_tools import search_docs
from .gtm_folders import create_folder
from .gtm_folders import get_folder_map
from .gtm_folders import list_folder_entities
from .gtm_folders import move_entities_to_folder
from .gtm_read import get_container_snapshot
from .gtm_read import get_tag
from .gtm_read import get_workspace_status
from .gtm_read import list_accounts
from .gtm_read import list_built_in_variables
from .gtm_read import list_containers
from .gtm_read import list_folders
from .gtm_read import list_tags
from .gtm_read import list_triggers
from .gtm_read import list_variables
from .gtm_read import list_workspaces
from .gtm_write import create_tag
from .gtm_write import create_trigger
from .gtm_write import create_variable
from .gtm_write import rename_entity
from .gtm_write import update_tag

#: Ferramentas de leitura do container, seguras para qualquer agente.
READ_TOOLS = [
    list_accounts,
    list_containers,
    list_workspaces,
    list_tags,
    get_tag,
    list_triggers,
    list_variables,
    list_built_in_variables,
    list_folders,
    get_workspace_status,
    get_container_snapshot,
]

#: Ferramentas de consulta a documentacao padrao.
DOC_TOOLS = [list_docs, read_doc, search_docs]

#: Ferramentas que criam ou alteram entidades no workspace.
WRITE_TOOLS = [create_tag, update_tag, create_trigger, create_variable, rename_entity]

#: Ferramentas de organizacao em pastas.
#: `list_folders` fica so em READ_TOOLS para nao duplicar nome de ferramenta
#: quando um agente recebe as duas listas.
FOLDER_TOOLS = [
    get_folder_map,
    list_folder_entities,
    create_folder,
    move_entities_to_folder,
]

__all__ = [
    "READ_TOOLS",
    "DOC_TOOLS",
    "WRITE_TOOLS",
    "FOLDER_TOOLS",
    "create_folder",
    "create_tag",
    "create_trigger",
    "create_variable",
    "get_container_snapshot",
    "get_folder_map",
    "get_tag",
    "get_workspace_status",
    "list_accounts",
    "list_built_in_variables",
    "list_containers",
    "list_docs",
    "list_folder_entities",
    "list_folders",
    "list_tags",
    "list_triggers",
    "list_variables",
    "list_workspaces",
    "move_entities_to_folder",
    "read_doc",
    "rename_entity",
    "save_custom_doc",
    "search_docs",
    "update_tag",
]
