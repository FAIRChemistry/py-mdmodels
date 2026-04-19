from __future__ import annotations

import inspect
import json
from datetime import date
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.tools import ToolResult
from mcp import types
from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator, model_validator

from ..constants import DATA_ENTRY_DESCRIPTION
from ._assets import load_html_asset
from .form_store import get_form, init_form_store, mark_form_completed, prune_stale_forms, track_open_form

FORM_VIEW_URI = "ui://mdmodels/data-entry-form.html"


class FormOption(BaseModel):
    value: str | int | float | bool
    label: str | None = None


class FormField(BaseModel):
    key: str = Field(
        min_length=1,
        description="Stable key used in the returned payload (for example 'methanol_concentration').",
    )
    label: str = Field(min_length=1, description="Human-readable field label shown to the user.")
    type: Literal[
        "string",
        "textarea",
        "integer",
        "number",
        "boolean",
        "enum",
        "date",
        "datetime",
    ]
    required: bool = True
    group: str | None = Field(
        default=None,
        description="Optional section heading. Fields with the same group are rendered together.",
    )
    description: str | None = Field(
        default=None, description="Optional helper text shown below the label."
    )
    placeholder: str | None = None
    default: Any = None
    enum: list[FormOption] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = Field(
        default=None,
        description="Optional regex pattern for string-like fields.",
    )
    step: float | None = None
    cols: list[int] | None = Field(
        default=None,
        description=(
            "Optional grid column placement as [span] or [start, span]. "
            "Only applied when request.n_cols defines a multi-column layout."
        ),
    )
    rows: list[int] | None = Field(
        default=None,
        description=(
            "Optional grid row placement as [span] or [start, span]. "
            "Only applied when request.n_cols defines a multi-column layout."
        ),
    )

    @model_validator(mode="after")
    def _validate_field(self):
        is_numeric = self.type in {"integer", "number"}
        is_textual = self.type in {"string", "textarea"}
        if self.type == "enum":
            if not self.enum:
                raise ValueError("Enum fields require at least one option.")
        elif self.enum:
            raise ValueError("Only fields with type='enum' may define enum options.")

        if not is_numeric and (
            self.min_value is not None or self.max_value is not None or self.step is not None
        ):
            raise ValueError(
                "min_value, max_value, and step are only valid for numeric fields."
            )

        if not is_textual and (
            self.min_length is not None
            or self.max_length is not None
            or self.pattern is not None
        ):
            raise ValueError(
                "min_length, max_length, and pattern are only valid for string/textarea fields."
            )

        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value cannot exceed max_value.")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length cannot exceed max_length.")

        for attr in ("cols", "rows"):
            spec = getattr(self, attr)
            if spec is None:
                continue
            if len(spec) not in {1, 2}:
                raise ValueError(f"{attr} must be [span] or [start, span].")
            if any(value < 1 for value in spec):
                raise ValueError(f"{attr} values must be positive integers.")
        return self


class DataEntryRequest(BaseModel):
    title: str = Field(min_length=1, description="Form title shown in the app frame.")
    instructions: str | None = Field(
        default=None,
        description="Short context text explaining what the user should provide.",
    )
    fields: list[FormField] = Field(
        min_length=1,
        max_length=24,
        description="Typed fields to render. Keep forms focused and compact.",
    )
    submit_label: str = Field(default="Send", min_length=1, max_length=40)
    n_cols: int | None = Field(
        default=None,
        ge=1,
        le=6,
        description=(
            "Optional number of columns for compact layout. "
            "If omitted, the form uses the default single-column layout."
        ),
    )
    form_id: str | None = Field(
        default=None,
        description="Optional stable id. If omitted, a UUID is generated.",
    )

    @field_validator("fields")
    @classmethod
    def _check_unique_keys(cls, fields: list[FormField]) -> list[FormField]:
        seen: set[str] = set()
        for field in fields:
            if field.key in seen:
                raise ValueError(f"Duplicate field key: '{field.key}'.")
            seen.add(field.key)
        return fields


class DataEntrySubmission(BaseModel):
    form_id: str
    values: dict[str, Any] = Field(default_factory=dict)
    request: DataEntryRequest | None = Field(
        default=None,
        description="Optional request snapshot for stateless validation across host/runtime boundaries.",
    )


class _PendingForm(BaseModel):
    created_at: datetime
    request: DataEntryRequest


_PENDING_FORMS: dict[str, _PendingForm] = {}
_OUTDATED_MESSAGE = "Data Entry is outdated"
_COMPLETED_MESSAGE = "Data Entry has been completed"


def register_data_entry_tool(*, app: FastMCP) -> None:
    init_form_store()

    @app.resource(
        FORM_VIEW_URI,
        app=AppConfig(
            csp=ResourceCSP(
                resourceDomains=["https://unpkg.com", "https://cdn.jsdelivr.net"]
            )
        ),
    )
    def _data_entry_resource() -> str:
        return DATA_ENTRY_HTML

    def data_entry(request: DataEntryRequest) -> ToolResult:
        form_ref_provided = request.form_id is not None
        form_id = request.form_id or str(uuid4())
        normalized = request.model_copy(update={"form_id": form_id})
        prune_stale_forms()
        stored = get_form(form_id)

        if form_ref_provided and stored is None:
            payload = {
                "_meta": {"form_id": form_id, "title": normalized.title},
                "state": "outdated",
                "message": _OUTDATED_MESSAGE,
            }
            return ToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload))]
            )

        if stored and stored["completed"]:
            payload = {
                "_meta": {"form_id": form_id, "title": normalized.title},
                "state": "completed",
                "message": _COMPLETED_MESSAGE,
                "submitted_payload": stored.get("submitted_payload"),
            }
            return ToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload))]
            )

        track_open_form(form_id)
        _PENDING_FORMS[form_id] = _PendingForm(
            created_at=datetime.utcnow(),
            request=normalized,
        )
        payload = {
            "_meta": {"form_id": form_id, "title": normalized.title},
            "state": "open",
            "request": normalized.model_dump(mode="json"),
        }
        return ToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))]
        )

    data_entry.__annotations__ = {
        "request": DataEntryRequest,
        "return": ToolResult,
    }  # type: ignore[assignment]
    data_entry.__signature__ = inspect.signature(data_entry)  # type: ignore[attr-defined]

    def submit_data_entry(submission: DataEntrySubmission) -> ToolResult:
        pending = _PENDING_FORMS.get(submission.form_id)
        request = pending.request if pending is not None else submission.request
        if request is None:
            raise ValueError(
                f"Unknown form_id '{submission.form_id}'. Ask the model to call Data_Entry again."
            )
        validated = _validate_submission(
            fields=request.fields,
            values=submission.values,
        )
        result_payload = {
            "kind": "data_entry_submission",
            "form_id": submission.form_id,
            "title": request.title,
            "data": validated,
        }
        mark_form_completed(submission.form_id, validated)
        if pending is not None:
            _PENDING_FORMS.pop(submission.form_id, None)
        return ToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result_payload))]
        )

    submit_data_entry.__annotations__ = {
        "submission": DataEntrySubmission,
        "return": ToolResult,
    }  # type: ignore[assignment]
    submit_data_entry.__signature__ = inspect.signature(submit_data_entry)  # type: ignore[attr-defined]

    app.tool(
        data_entry,
        name="Data_Entry",
        description=DATA_ENTRY_DESCRIPTION,
        app=AppConfig(resourceUri=FORM_VIEW_URI),
    )
    app.tool(
        submit_data_entry,
        name="Submit_Data_Entry",
        description=(
            "Callback for Data_Entry submissions. Intended to be called by the form app to "
            "validate and finalize typed user input."
        ),
        app=AppConfig(visibility=["model", "app"]),
    )


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raise ValueError("Expected a boolean value.")


def _validate_submission(*, fields: list[FormField], values: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    errors: list[str] = []

    for field in fields:
        raw_present = field.key in values
        raw_value = values.get(field.key)
        if (not raw_present or raw_value in {"", None}) and field.required:
            errors.append(f"{field.label}: value is required.")
            continue
        if not raw_present or raw_value in {"", None}:
            out[field.key] = None
            continue

        try:
            non_null_value = raw_value
            if non_null_value is None:
                raise ValueError("Value cannot be null.")
            if field.type in {"string", "textarea", "date", "datetime"}:
                value = str(non_null_value)
                if field.min_length is not None and len(value) < field.min_length:
                    raise ValueError(f"Must be at least {field.min_length} characters.")
                if field.max_length is not None and len(value) > field.max_length:
                    raise ValueError(f"Must be at most {field.max_length} characters.")
                if field.pattern:
                    import re

                    if re.fullmatch(field.pattern, value) is None:
                        raise ValueError("Does not match the required pattern.")
                if field.type == "date":
                    date.fromisoformat(value)
                if field.type == "datetime":
                    datetime.fromisoformat(value)
            elif field.type == "integer":
                value = int(non_null_value)
            elif field.type == "number":
                value = float(non_null_value)
            elif field.type == "boolean":
                value = _coerce_bool(non_null_value)
            elif field.type == "enum":
                allowed = [opt.value for opt in field.enum]
                value = _coerce_enum_value(non_null_value, allowed)
                if value not in allowed:
                    raise ValueError(
                        f"Invalid option '{value}'. Allowed values: {allowed}."
                    )
            else:
                raise ValueError(f"Unsupported type '{field.type}'.")

            if field.type in {"integer", "number"}:
                numeric_value = float(value)
                if field.min_value is not None and numeric_value < field.min_value:
                    raise ValueError(f"Must be >= {field.min_value}.")
                if field.max_value is not None and numeric_value > field.max_value:
                    raise ValueError(f"Must be <= {field.max_value}.")

            out[field.key] = value
        except (TypeError, ValueError) as exc:
            errors.append(f"{field.label}: {exc}")

    if errors:
        raise ValueError("Invalid form submission:\n- " + "\n- ".join(errors))
    return out


def _coerce_enum_value(value: Any, allowed: list[Any]) -> Any:
    if value in allowed:
        return value
    for option in allowed:
        try:
            coerced = TypeAdapter(type(option)).validate_python(value)
        except ValidationError:
            continue
        if coerced == option:
            return coerced
    return value


def _load_data_entry_html() -> str:
    return load_html_asset("data_entry_form.html")


DATA_ENTRY_HTML = _load_data_entry_html()
