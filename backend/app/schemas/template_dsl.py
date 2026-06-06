from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


JD_FIELD_NAMES = {
    "title",
    "job_summary",
    "about_company",
    "roles_and_responsibilities",
    "required_skills",
    "preferred_skills",
    "technical_skills",
    "soft_skills",
    "qualifications",
    "education",
    "experience",
    "location",
    "employment_type",
    "notice_period",
    "salary_range",
    "benefits",
    "project_details",
    "team_details",
    "industry",
    "department",
    "reporting_manager",
    "travel_requirements",
    "work_mode",
    "certifications",
    "languages",
    "selection_process",
    "additional_information",
    "contact_information",
    "metadata",
}


class BoxStyle(BaseModel):
    background_color: str | None = None
    border_color: str | None = None
    border_width: float = Field(default=0, ge=0, le=8)
    radius: float = Field(default=0, ge=0, le=30)
    padding: float = Field(default=0, ge=0, le=72)


class TextStyle(BaseModel):
    font_name: str = "Helvetica"
    font_size: float = Field(default=9, ge=5, le=48)
    leading: float | None = Field(default=None, ge=6, le=60)
    color: str = "#222222"
    alignment: Literal["LEFT", "CENTER", "RIGHT", "JUSTIFY"] = "LEFT"
    space_before: float = Field(default=0, ge=0, le=72)
    space_after: float = Field(default=6, ge=0, le=72)
    uppercase: bool = False


class DividerStyle(BaseModel):
    color: str = "#D4D7E0"
    width: float = Field(default=0.8, ge=0.1, le=8)
    space_before: float = Field(default=6, ge=0, le=72)
    space_after: float = Field(default=6, ge=0, le=72)


class TableStyleDef(BaseModel):
    header_background: str | None = "#E8ECF2"
    border_color: str = "#D4D7E0"
    text_color: str = "#222222"
    cell_padding: float = Field(default=6, ge=0, le=24)


class TemplateBlock(BaseModel):
    type: Literal[
        "field",
        "paragraph",
        "section",
        "bullet_list",
        "table",
        "columns",
        "card",
        "banner",
        "divider",
        "spacer",
        "logo",
        "page_number",
    ]
    field: str | None = None
    label: str | None = None
    text: str | None = None
    fields: list[str] = Field(default_factory=list)
    blocks: list["TemplateBlock"] = Field(default_factory=list)
    columns: list[list["TemplateBlock"]] = Field(default_factory=list)
    widths: list[float] = Field(default_factory=list)
    style: TextStyle | None = None
    box: BoxStyle | None = None
    divider: DividerStyle | None = None
    table: TableStyleDef | None = None
    height: float = Field(default=8, ge=0, le=144)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str | None) -> str | None:
        if value and value not in JD_FIELD_NAMES:
            raise ValueError(f"Unsupported JD field: {value}")
        return value

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if value not in JD_FIELD_NAMES]
        if invalid:
            raise ValueError(f"Unsupported JD fields: {', '.join(invalid)}")
        return values


class HeaderFooterDef(BaseModel):
    enabled: bool = True
    blocks: list[TemplateBlock] = Field(default_factory=list)
    height: float = Field(default=44, ge=0, le=160)


class TemplateDefinition(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    name: str = "Custom JD Template"
    description: str | None = None
    page_size: Literal["letter", "a4"] = "letter"
    margins: dict[str, float] = Field(default_factory=lambda: {"top": 54, "right": 54, "bottom": 54, "left": 54})
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, TextStyle] = Field(default_factory=dict)
    spacing: dict[str, float] = Field(default_factory=dict)
    header: HeaderFooterDef | None = None
    footer: HeaderFooterDef | None = None
    sections: list[TemplateBlock] = Field(default_factory=list)
    section_order: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("margins")
    @classmethod
    def validate_margins(cls, margins: dict[str, float]) -> dict[str, float]:
        normalized = {**{"top": 54, "right": 54, "bottom": 54, "left": 54}, **margins}
        for key, value in normalized.items():
            if key not in {"top", "right", "bottom", "left"}:
                raise ValueError(f"Unsupported margin: {key}")
            if value < 18 or value > 144:
                raise ValueError(f"Margin {key} must be between 18 and 144")
        return normalized

    @field_validator("section_order")
    @classmethod
    def validate_section_order(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if value not in JD_FIELD_NAMES]
        if invalid:
            raise ValueError(f"Unsupported section_order fields: {', '.join(invalid)}")
        return values


TemplateBlock.model_rebuild()
