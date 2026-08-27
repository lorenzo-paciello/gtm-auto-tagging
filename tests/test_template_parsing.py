"""Guard the community-template parameter parser.

`get_template_spec` reads a template's parameter contract out of its raw
`templateData` (.tpl format). Getting this wrong is silent: the agent builds
`parameters_json` with the wrong key names, the API accepts unknown keys
without complaint, and the resulting tag does nothing.

The shapes covered here are the ones real vendor templates use -- GROUP
wrappers whose subParams are the actual API keys, SELECT dropdowns with a fixed
value set, and PARAM_TABLE columns.

Runs with pytest, or standalone: `python tests/test_template_parsing.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.gtm_templates import (  # noqa: E402
    parse_template_parameters,
    resolve_tag_type,
)

VENDOR_SHAPED = """___INFO___

{
  "type": "TAG",
  "id": "cvt_temp_public_id",
  "version": 1,
  "displayName": "Fake Vendor Pixel",
  "description": "Shaped like a real vendor template.",
  "containerContexts": ["WEB"]
}


___TEMPLATE_PARAMETERS___

[
  {
    "type": "TEXT",
    "name": "pixelCode",
    "displayName": "Pixel Code",
    "simpleValueType": true,
    "valueValidators": [{"type": "NON_EMPTY"}]
  },
  {
    "type": "SELECT",
    "name": "eventType",
    "displayName": "Event Type",
    "selectItems": [
      {"value": "page", "displayValue": "Page View"},
      {"value": "purchase", "displayValue": "Purchase"}
    ],
    "simpleValueType": true
  },
  {
    "type": "GROUP",
    "name": "advancedGroup",
    "displayName": "Advanced",
    "subParams": [
      {
        "type": "TEXT",
        "name": "currency",
        "displayName": "Currency",
        "simpleValueType": true,
        "defaultValue": "USD"
      },
      {
        "type": "PARAM_TABLE",
        "name": "customProperties",
        "displayName": "Custom Properties",
        "paramTableColumns": [
          {"param": {"type": "TEXT", "name": "propName"}, "isUnique": true},
          {"param": {"type": "TEXT", "name": "propValue"}}
        ]
      }
    ]
  }
]


___SANDBOXED_JS_FOR_WEB_TEMPLATE___

data.gtmOnSuccess();
"""


def test_required_parameters_detected():
    parsed = parse_template_parameters(VENDOR_SHAPED)
    assert parsed["required_parameters"] == ["pixelCode"]


def test_group_subparams_are_flattened():
    """A GROUP is presentational; its subParams are the real API keys."""
    parsed = parse_template_parameters(VENDOR_SHAPED)
    names = [p["name"] for p in parsed["parameters"]]
    assert "currency" in names, "GROUP subParams must be flattened"
    assert "customProperties" in names
    assert "advancedGroup" not in names, "the GROUP itself is not an API key"


def test_select_allowed_values():
    parsed = parse_template_parameters(VENDOR_SHAPED)
    select = next(p for p in parsed["parameters"] if p["name"] == "eventType")
    assert [a["value"] for a in select["allowed_values"]] == ["page", "purchase"]


def test_param_table_columns():
    parsed = parse_template_parameters(VENDOR_SHAPED)
    table = next(p for p in parsed["parameters"] if p["name"] == "customProperties")
    assert table["table_columns"] == ["propName", "propValue"]


def test_default_values_preserved():
    parsed = parse_template_parameters(VENDOR_SHAPED)
    currency = next(p for p in parsed["parameters"] if p["name"] == "currency")
    assert currency["default_value"] == "USD"


def test_info_section_parsed():
    parsed = parse_template_parameters(VENDOR_SHAPED)
    assert parsed["display_name"] == "Fake Vendor Pixel"
    assert parsed["container_contexts"] == ["WEB"]
    assert parsed["parse_error"] is None


def test_malformed_template_data_does_not_raise():
    for bad in ("", "not a template", "___INFO___\n{broken json"):
        parsed = parse_template_parameters(bad)
        assert parsed["parameters"] == []


def test_gallery_template_uses_its_declared_id():
    """A gallery template's type is cvt_<galleryTemplateId>, NOT cvt_<container>_<id>.

    Getting this wrong is what produced `400 Unknown entity type` and the false
    report that the API cannot create community-template tags. Values below are
    the real ones from the official templates.
    """
    for gallery_id, template_id in (("MRQN8", "54"), ("5RM3Q", "52"), ("NGMPN", "51")):
        template = {
            "templateId": template_id,
            "containerId": "261951688",
            "galleryReference": {"galleryTemplateId": gallery_id, "owner": "vendor"},
            "templateData": (
                '___INFO___\n\n{"type": "TAG", "id": "cvt_%s", "version": 1}\n\n'
                "___TEMPLATE_PARAMETERS___\n\n[]\n" % gallery_id
            ),
        }
        assert resolve_tag_type(template) == f"cvt_{gallery_id}"


def test_custom_template_uses_container_and_template_id():
    """A hand-written template carries a placeholder id until GTM assigns one."""
    template = {
        "templateId": "49",
        "containerId": "261951688",
        "templateData": (
            '___INFO___\n\n{"type": "TAG", "id": "cvt_temp_public_id"}\n\n'
            "___TEMPLATE_PARAMETERS___\n\n[]\n"
        ),
    }
    assert resolve_tag_type(template) == "cvt_261951688_49"


def test_resolve_falls_back_when_info_is_missing():
    assert (
        resolve_tag_type({"templateId": "9", "containerId": "111", "templateData": ""})
        == "cvt_111_9"
    )
    assert (
        resolve_tag_type(
            {
                "templateId": "9",
                "containerId": "111",
                "templateData": "",
                "galleryReference": {"galleryTemplateId": "ABC12"},
            }
        )
        == "cvt_ABC12"
    )


def test_format_validators_are_extracted():
    """Templates validate format, not just presence. Real Pinterest/Meta rules."""
    data = """___INFO___

{"type": "TAG", "id": "cvt_NGMPN"}


___TEMPLATE_PARAMETERS___

[
  {
    "type": "TEXT",
    "name": "tagId",
    "simpleValueType": true,
    "valueValidators": [
      {"type": "NON_EMPTY"},
      {"args": ["26\\\\d{11}"], "type": "REGEX"}
    ]
  },
  {
    "type": "TEXT",
    "name": "currency",
    "simpleValueType": true,
    "valueValidators": [
      {"args": [3, 3], "errorMessage": "Please enter a valid currency.", "type": "STRING_LENGTH"}
    ]
  },
  {
    "type": "TEXT",
    "name": "order_quantity",
    "simpleValueType": true,
    "valueValidators": [{"type": "NUMBER"}]
  }
]
"""
    parsed = parse_template_parameters(data)
    by_name = {p["name"]: p for p in parsed["parameters"]}

    assert by_name["tagId"]["required"] is True
    assert by_name["tagId"]["pattern"] == r"26\d{11}"
    assert by_name["currency"]["min_length"] == 3
    assert by_name["currency"]["max_length"] == 3
    assert by_name["currency"]["length_error"] == "Please enter a valid currency."
    assert by_name["order_quantity"]["must_be_number"] is True


def test_radio_choices_are_extracted():
    """RADIO stores its options under `radioItems`, SELECT under `selectItems`.

    Reading only `selectItems` silently drops the valid values of every radio
    parameter, and an agent with no value list invents one. Values below are
    real: Meta's eventName and TikTok's hash.
    """
    data = """___INFO___

{"type": "TAG", "id": "cvt_X"}


___TEMPLATE_PARAMETERS___

[
  {
    "type": "RADIO",
    "name": "eventName",
    "displayName": "Event Name",
    "radioItems": [
      {"value": "standard", "displayValue": "Standard"},
      {"value": "custom", "displayValue": "Custom"},
      {"value": "variable", "displayValue": "From Variable"}
    ],
    "simpleValueType": true
  },
  {
    "type": "SELECT",
    "name": "event",
    "selectItems": [{"value": "CompletePayment", "displayValue": "Purchase"}],
    "simpleValueType": true
  }
]
"""
    by_name = {p["name"]: p for p in parse_template_parameters(data)["parameters"]}
    assert [a["value"] for a in by_name["eventName"]["allowed_values"]] == [
        "standard",
        "custom",
        "variable",
    ]
    assert [a["value"] for a in by_name["event"]["allowed_values"]] == ["CompletePayment"]


def test_vendor_help_makes_an_unknown_template_self_describing():
    """An agent seeing a template for the first time relies on these fields."""
    data = """___INFO___

{"type": "TAG", "id": "cvt_X"}


___TEMPLATE_PARAMETERS___

[
  {
    "type": "TEXT",
    "name": "pixel_code",
    "displayName": "Pixel ID",
    "help": "You can find your <b>Pixel ID</b> in\\n  Events Manager",
    "valueHint": "CD9079RC77U0N3GBV16Y",
    "simpleValueType": true
  },
  {
    "type": "TEXT",
    "name": "email",
    "displayName": "Email",
    "enablingConditions": [
      {"paramName": "hash", "paramValue": "non-hashed", "type": "EQUALS"}
    ],
    "simpleValueType": true
  }
]
"""
    by_name = {p["name"]: p for p in parse_template_parameters(data)["parameters"]}
    # HTML and newlines are flattened so the text is readable in a tool result.
    assert by_name["pixel_code"]["help"] == "You can find your Pixel ID in Events Manager"
    assert by_name["pixel_code"]["value_hint"] == "CD9079RC77U0N3GBV16Y"
    assert by_name["email"]["only_applies_when"] == ["hash equals non-hashed"]


def test_label_params_are_not_api_keys():
    """Vendor templates carry LABEL help-text entries; they are not parameters."""
    data = """___INFO___

{"type": "TAG", "id": "cvt_X"}


___TEMPLATE_PARAMETERS___

[
  {"type": "LABEL", "name": "Parameter Override Description", "displayName": "help"},
  {"type": "TEXT", "name": "pixel_code", "simpleValueType": true}
]
"""
    names = [p["name"] for p in parse_template_parameters(data)["parameters"]]
    assert names == ["pixel_code"]


def test_localized_fields_are_reduced_to_their_text():
    """A translated template declares display text as an object, not a string.

    Passing it through raw put a Python dict repr into the error messages the
    agent reads back: ```bundleURL` ({'text': 'Bundle URL',
    'translations': [...]}) is required``. One real template carried 55 of
    these fields.
    """
    data = _template_data_for_test("[{\"type\": \"TEXT\", \"name\": \"bundleURL\", \"displayName\": {\"text\": \"Bundle URL\", \"translations\": [{\"locale\": \"tr\", \"text\": \"Paket URL\"}]}, \"help\": {\"text\": \"The <b>address</b> of your code\", \"translations\": [{\"locale\": \"tr\", \"text\": \"Kodunuzun adresi\"}]}, \"simpleValueType\": true, \"valueValidators\": [{\"type\": \"NON_EMPTY\"}]}, {\"type\": \"SELECT\", \"name\": \"ad_storage\", \"displayName\": {\"text\": \"ad_storage\", \"translations\": []}, \"selectItems\": [{\"value\": \"essential\", \"displayValue\": {\"text\": \"Essential Cookies\", \"translations\": []}}, {\"value\": \"none\", \"displayValue\": \"None\"}], \"simpleValueType\": true}, {\"type\": \"CHECKBOX\", \"name\": \"loadSDK\", \"checkboxText\": {\"text\": \"Load JS\", \"translations\": []}, \"simpleValueType\": true}]")
    parsed = parse_template_parameters(data)
    by_name = {p['name']: p for p in parsed['parameters']}

    assert by_name['bundleURL']['display_name'] == 'Bundle URL'
    assert by_name['bundleURL']['help'] == 'The address of your code'
    assert by_name['ad_storage']['display_name'] == 'ad_storage'
    assert by_name['loadSDK']['checkbox_text'] == 'Load JS'

    labels = [a['label'] for a in by_name['ad_storage']['allowed_values']]
    assert labels == ['Essential Cookies', 'None'], (
        'localized and plain option labels must both come out as strings'
    )

    for entry in parsed['parameters']:
        for field in ('display_name', 'help', 'checkbox_text', 'value_hint'):
            value = entry.get(field)
            assert value is None or isinstance(value, str), (
                f'{entry["name"]}.{field} leaked a {type(value).__name__}'
            )


def _template_data_for_test(params_json):
    nl = chr(10)
    return nl.join([
        '___INFO___', '',
        '{"type": "TAG", "id": "cvt_X"}', '',
        '___TEMPLATE_PARAMETERS___', '',
        params_json, '',
    ])



if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}\n      {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
