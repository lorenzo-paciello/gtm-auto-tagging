"""Function tools exposed to the agents."""

from .docs_tools import list_docs
from .docs_tools import read_doc
from .docs_tools import save_custom_doc
from .docs_tools import search_docs
from .gtm_folders import create_folder
from .gtm_folders import get_folder_map
from .gtm_folders import list_folder_entities
from .gtm_folders import move_entities_to_folder
from .gtm_duplicates import find_duplicate_tags
from .gtm_creation_gate import preview_tag_conflicts
from .gtm_identity_audit import check_id_consistency
from .gtm_prerequisites import check_tagging_prerequisites
from .gtm_read import find_broken_references
from .gtm_read import get_container_snapshot
from .gtm_read import get_tag
from .gtm_read import get_workspace_status
from .gtm_read import list_accounts
from .gtm_read import list_built_in_triggers
from .gtm_read import list_built_in_variables
from .gtm_read import list_containers
from .gtm_read import list_folders
from .gtm_read import list_tags
from .gtm_read import list_triggers
from .gtm_read import list_variables
from .gtm_read import list_workspaces
from .gtm_templates import get_template_spec
from .gtm_templates import list_templates
from .tag_specs import get_entity_spec
from .gtm_write import create_tag
from .gtm_write import create_trigger
from .gtm_write import create_variable
from .gtm_write import rename_entity
from .gtm_write import update_tag

#: Container read tools. Safe for any agent.
READ_TOOLS = [
    list_accounts,
    list_containers,
    list_workspaces,
    list_tags,
    get_tag,
    list_triggers,
    list_built_in_triggers,
    list_variables,
    list_built_in_variables,
    list_folders,
    list_templates,
    get_template_spec,
    check_tagging_prerequisites,
    check_id_consistency,
    find_broken_references,
    find_duplicate_tags,
    preview_tag_conflicts,
    get_workspace_status,
    get_container_snapshot,
]

#: Standard-documentation lookup tools.
DOC_TOOLS = [list_docs, read_doc, search_docs]

#: Tools that create or change entities in the workspace. `get_entity_spec`
#: rides along because it is what stops a create call from being rejected.
WRITE_TOOLS = [
    get_entity_spec,
    create_tag,
    update_tag,
    create_trigger,
    create_variable,
    rename_entity,
]

#: Folder organization tools.
#: `list_folders` lives only in READ_TOOLS so no agent receives the same tool
#: name twice when it is given both lists.
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
    "check_id_consistency",
    "check_tagging_prerequisites",
    "create_folder",
    "create_tag",
    "create_trigger",
    "create_variable",
    "find_broken_references",
    "find_duplicate_tags",
    "preview_tag_conflicts",
    "get_container_snapshot",
    "get_entity_spec",
    "get_folder_map",
    "get_tag",
    "get_template_spec",
    "get_workspace_status",
    "list_accounts",
    "list_built_in_triggers",
    "list_built_in_variables",
    "list_containers",
    "list_docs",
    "list_folder_entities",
    "list_folders",
    "list_tags",
    "list_templates",
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
