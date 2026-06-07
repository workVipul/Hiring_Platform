# HTML/CSS Template Migration Plan

Date: 2026-06-07

## Goal

Move custom JD templates from the legacy `TemplateDefinition` DSL plus custom ReportLab renderer to reusable HTML/CSS templates rendered with Jinja2 and WeasyPrint.

The LLM is used only when an admin uploads a template PDF. Normal preview/publish PDF generation loads stored HTML/CSS and renders it with JD data.

## Database Changes

Add nullable columns to `jd_templates`:

```sql
ALTER TABLE jd_templates ADD COLUMN template_html TEXT;
ALTER TABLE jd_templates ADD COLUMN template_css TEXT;
ALTER TABLE jd_templates ADD COLUMN mapped_fields JSON;
```

The local dev app also applies these columns at startup in `app.main.ensure_jd_template_module_column()` because this repo does not currently have Alembic configured.

Keep existing columns during migration:

```text
definition_json
version
prompt
```

`definition_json` remains for legacy fallback only.

## Feature Flag

Default:

```env
ENABLE_LEGACY_DSL=false
```

Behavior:

- `false`: custom template uploads generate `template_html`, `template_css`, and `mapped_fields`.
- `false`: custom template preview/publish uses Jinja2 + WeasyPrint.
- `true`: custom template uploads and rendering use the old DSL pipeline.

## Upload Pipeline

New default flow:

```text
Admin PDF upload
PDF -> PNG
Gemini vision request
JSON response: { html, css, mapped_fields }
HTML/CSS sanitization
Placeholder validation
Store template_html/template_css/mapped_fields
```

Validation rejects:

- empty HTML
- empty CSS
- no placeholders
- fewer than 3 mapped fields
- unsupported placeholders
- unsafe HTML/CSS constructs

Logs:

```text
TEMPLATE_HTML_LENGTH
TEMPLATE_CSS_LENGTH
MAPPED_FIELDS
HTML_TEMPLATE_STORED
```

## Rendering Pipeline

For `metadata.template = custom-<id>`:

```text
Load template_html/template_css/mapped_fields
Build JD field context
Render Jinja2 template
Wrap CSS + HTML
WeasyPrint HTML -> PDF
```

Built-in templates continue using ReportLab.

## Rollout

1. Deploy DB columns.
2. Deploy code with `ENABLE_LEGACY_DSL=true` if you need old templates to keep working immediately.
3. Test new uploads in staging with `ENABLE_LEGACY_DSL=false`.
4. Re-upload or migrate important custom templates into HTML/CSS format.
5. Switch production to `ENABLE_LEGACY_DSL=false`.
6. After all custom templates have HTML/CSS data, remove legacy DSL code in a later cleanup.

## Notes

Old custom templates with only `definition_json` will not render when `ENABLE_LEGACY_DSL=false`. Either keep the flag enabled during migration or re-upload those templates so the HTML/CSS fields are populated.
