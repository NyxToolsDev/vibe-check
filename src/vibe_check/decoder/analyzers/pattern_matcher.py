"""Heuristic pattern matcher — infers file/function purpose from patterns."""

from __future__ import annotations


# Maps import module names to purpose descriptions
_IMPORT_PATTERNS: dict[str, str] = {
    "flask": "Flask web application",
    "fastapi": "FastAPI web application",
    "django": "Django web application",
    "click": "CLI command definition",
    "argparse": "CLI argument parsing",
    "typer": "CLI command definition",
    "pytest": "test suite",
    "unittest": "test suite",
    "sqlalchemy": "database ORM layer",
    "alembic": "database migration",
    "celery": "async task queue worker",
    "redis": "Redis cache/queue integration",
    "httpx": "HTTP client",
    "requests": "HTTP client",
    "aiohttp": "async HTTP client/server",
    "pydantic": "data validation/serialization",
    "marshmallow": "data serialization",
    "logging": "logging configuration",
    "pathlib": "file system operations",
    "subprocess": "shell command execution",
    "asyncio": "async/await orchestration",
    "threading": "multi-threaded processing",
    "json": "JSON data handling",
    "csv": "CSV data handling",
    "yaml": "YAML configuration handling",
    "toml": "TOML configuration handling",
    "jinja2": "template rendering",
    "rich": "terminal UI rendering",
    "cryptography": "encryption/cryptographic operations",
    "jwt": "JWT token handling",
    "passlib": "password hashing",
    "smtplib": "email sending",
    "boto3": "AWS SDK integration",
    "stripe": "Stripe payment integration",
    "pydicom": "DICOM medical imaging",
    "hl7": "HL7 healthcare messaging",
    "fhir": "FHIR healthcare interoperability",
}

# Maps class base names to purpose descriptions
_CLASS_BASE_PATTERNS: dict[str, str] = {
    "ABC": "abstract base class",
    "BaseModel": "Pydantic data model",
    "Model": "database model",
    "TestCase": "test case class",
    "Exception": "custom exception",
    "Enum": "enumeration",
    "Protocol": "protocol/interface definition",
    "TypedDict": "typed dictionary schema",
}

# Maps decorator names to purpose descriptions
_DECORATOR_PATTERNS: dict[str, str] = {
    "app.route": "web route handler",
    "app.get": "GET endpoint handler",
    "app.post": "POST endpoint handler",
    "app.put": "PUT endpoint handler",
    "app.delete": "DELETE endpoint handler",
    "router.get": "GET endpoint handler",
    "router.post": "POST endpoint handler",
    "main.command": "CLI command",
    "click.command": "CLI command",
    "click.group": "CLI command group",
    "property": "computed property",
    "staticmethod": "static method",
    "classmethod": "class method",
    "abstractmethod": "abstract method (must be overridden)",
    "pytest.fixture": "test fixture",
    "pytest.mark.parametrize": "parameterized test",
    "register_scanner": "registered scanner plugin",
    "dataclass": "data class",
    "cached_property": "cached computed property",
}

# Maps filename patterns to purpose descriptions
_FILENAME_PATTERNS: list[tuple[str, str]] = [
    ("__init__", "package initializer"),
    ("__main__", "package entry point"),
    ("conftest", "pytest configuration and shared fixtures"),
    ("test_", "test module"),
    ("_test", "test module"),
    ("cli", "command-line interface"),
    ("config", "configuration"),
    ("settings", "application settings"),
    ("models", "data models"),
    ("schemas", "data schemas/validation"),
    ("routes", "web route definitions"),
    ("views", "view handlers"),
    ("middleware", "request/response middleware"),
    ("utils", "utility functions"),
    ("helpers", "helper functions"),
    ("constants", "constant definitions"),
    ("exceptions", "custom exception definitions"),
    ("migrations", "database migration"),
    ("tasks", "async/background tasks"),
    ("serializers", "data serialization"),
    ("admin", "admin interface configuration"),
    ("auth", "authentication/authorization"),
    ("permissions", "permission/access control"),
    ("validators", "input validation"),
    ("factories", "test data factories"),
    ("fixtures", "test fixtures"),
    ("setup", "package/project setup"),
    ("registry", "plugin/component registry"),
    ("runner", "orchestrator/runner"),
    ("engine", "core processing engine"),
    ("scanner", "code scanning/analysis"),
    ("reporter", "output/report generation"),
    ("parser", "input parsing"),
    ("walker", "file/directory traversal"),
    ("license", "license validation"),
    ("scoring", "scoring/grading logic"),
]


def infer_file_summary(
    filename: str,
    imports: list[str],
    class_names: list[str],
    class_bases: list[list[str]],
    function_names: list[str],
    decorators: list[list[str]],
    has_main_guard: bool,
) -> str:
    """Infer a plain-English summary of what a file does.

    Uses a layered heuristic approach:
    1. Filename patterns (most specific)
    2. Import-based inference (what libraries it uses)
    3. Class inheritance patterns
    4. Decorator patterns
    5. Fallback to generic description
    """
    parts: list[str] = []

    # Layer 1: Filename
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    for pattern, desc in _FILENAME_PATTERNS:
        if pattern in stem.lower():
            parts.append(desc)
            break

    # Layer 2: Dominant import
    import_hits: list[str] = []
    for imp in imports:
        top_module = imp.split(".")[0]
        if top_module in _IMPORT_PATTERNS:
            import_hits.append(_IMPORT_PATTERNS[top_module])
    if import_hits:
        # Deduplicate while preserving order
        seen: set[str] = set()
        for hit in import_hits:
            if hit not in seen:
                seen.add(hit)
                parts.append(hit)

    # Layer 3: Class bases
    for bases in class_bases:
        for base in bases:
            base_name = base.rsplit(".", 1)[-1]
            if base_name in _CLASS_BASE_PATTERNS:
                parts.append(_CLASS_BASE_PATTERNS[base_name])

    # Layer 4: Decorators
    for dec_list in decorators:
        for dec in dec_list:
            if dec in _DECORATOR_PATTERNS:
                parts.append(_DECORATOR_PATTERNS[dec])
                break

    # Layer 5: Entry point detection
    if has_main_guard:
        parts.append("executable script")

    if not parts:
        if function_names:
            return f"Module with {len(function_names)} function(s)"
        if class_names:
            return f"Module defining {', '.join(class_names)}"
        return "Source file"

    # Deduplicate and join
    seen_parts: set[str] = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen_parts:
            seen_parts.add(p)
            unique.append(p)

    return "; ".join(unique[:3]).capitalize()


def infer_function_description(
    name: str,
    decorators: list[str],
    docstring: str | None,
    calls: list[str],
) -> str:
    """Infer a description for a function.

    Priority: docstring > decorator > naming convention > fallback.
    """
    if docstring:
        # Use first line of docstring
        first_line = docstring.split("\n")[0].strip()
        if first_line:
            return first_line

    # Check decorators
    for dec in decorators:
        if dec in _DECORATOR_PATTERNS:
            return _DECORATOR_PATTERNS[dec].capitalize()

    # Naming conventions
    if name.startswith("test_"):
        return f"Tests {name[5:].replace('_', ' ')}"
    if name.startswith("_"):
        return "Internal helper function"
    if name.startswith("get_") or name.startswith("fetch_"):
        return f"Retrieves {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("set_") or name.startswith("update_"):
        return f"Updates {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("create_") or name.startswith("make_") or name.startswith("build_"):
        return f"Creates {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("delete_") or name.startswith("remove_"):
        return f"Removes {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("is_") or name.startswith("has_") or name.startswith("can_"):
        return f"Checks whether {name.replace('_', ' ')}"
    if name.startswith("validate_") or name.startswith("check_"):
        return f"Validates {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("parse_"):
        return f"Parses {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("render_"):
        return f"Renders {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("handle_"):
        return f"Handles {name.split('_', 1)[1].replace('_', ' ')}"
    if name.startswith("init_") or name == "__init__":
        return "Initializer"
    if name == "__str__" or name == "__repr__":
        return "String representation"

    return ""


def infer_class_description(
    name: str,
    bases: list[str],
    docstring: str | None,
) -> str:
    """Infer a description for a class."""
    if docstring:
        first_line = docstring.split("\n")[0].strip()
        if first_line:
            return first_line

    for base in bases:
        base_name = base.rsplit(".", 1)[-1]
        if base_name in _CLASS_BASE_PATTERNS:
            return f"{name} — {_CLASS_BASE_PATTERNS[base_name]}"

    return ""
