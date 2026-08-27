# Audit checklist - <BUSINESS NAME>

> Version 1.0 - updated <YYYY-MM-DD> - owner: <NAME>

Each item gets OK / Fix / N/A, with evidence (entity id).

## 1. Foundation

- [ ] Exactly one Google base tag per destination, with a firing trigger
- [ ] No duplicate base tags pointing at the same measurement id
- [ ] Conversion Linker present when Google Ads or Floodlight exist
- [ ] Consent Initialization fires before everything else
- [ ] No event tag whose product foundation is missing

## 2. Coverage

- [ ] Every critical event in the dictionary is implemented
- [ ] Each implemented event carries its required parameters
- [ ] Paid media conversions cover the same business events as GA4
- [ ] No important event depends solely on Custom HTML

## 3. Configuration

- [ ] Measurement IDs and conversion IDs come from variables, not hardcoded
- [ ] Ecommerce tags read the `ecommerce` object from the dataLayer
- [ ] No tag with an empty `firingTriggerId`
- [ ] No paused tag without a justification in `notes`

## 4. Consent and privacy

- [ ] Consent Mode configured, with Consent Initialization first
- [ ] Media tags declare `consentSettings`
- [ ] No plain personal data (email, phone, national id) being sent
- [ ] Enhanced Conversions use hashed data or the native `user_data` field

## 5. Organization

- [ ] Every entity is in a folder
- [ ] Names follow `naming_conventions.md`
- [ ] No duplicate names among tags, triggers or variables
- [ ] `notes` filled on the critical entities

## 6. Hygiene

- [ ] No orphan triggers
- [ ] No unused variables
- [ ] No active Universal Analytics tags
- [ ] No Custom HTML doing what a native tag already does
- [ ] No pending merge conflicts in the workspace

## 7. Publishing

- [ ] Recent versions have a name and description
- [ ] There is a staging environment or a Preview process before publishing
- [ ] Pending workspace changes have been reviewed

## Findings

| Severity | Entity (id) | Problem | Recommendation | Owner |
| --- | --- | --- | --- | --- |
| | | | | |
