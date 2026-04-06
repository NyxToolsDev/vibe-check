"""Heuristic pattern matcher — infers file/function purpose from patterns.

This is the core intelligence of the free tier. The better these heuristics,
the more useful the decoder output is without any AI backend.
"""

from __future__ import annotations


# Maps import module names to plain-English purpose descriptions
_IMPORT_HINTS: dict[str, str] = {
    "flask": "handles web requests using Flask",
    "fastapi": "handles web requests using FastAPI",
    "django": "part of the Django web application",
    "click": "defines terminal commands you can run",
    "argparse": "defines terminal commands you can run",
    "typer": "defines terminal commands you can run",
    "pytest": "contains automated tests",
    "unittest": "contains automated tests",
    "sqlalchemy": "talks to a database",
    "alembic": "manages database schema changes",
    "celery": "runs background tasks in a queue",
    "redis": "connects to Redis for caching or messaging",
    "httpx": "makes HTTP requests to external services",
    "requests": "makes HTTP requests to external services",
    "aiohttp": "handles async HTTP requests",
    "pydantic": "validates and structures data",
    "marshmallow": "validates and structures data",
    "logging": "sets up error and activity logging",
    "subprocess": "runs system commands from Python",
    "asyncio": "coordinates async operations",
    "threading": "runs things in parallel using threads",
    "json": "reads or writes JSON data",
    "csv": "reads or writes CSV files",
    "yaml": "reads or writes YAML config files",
    "toml": "reads or writes TOML config files",
    "jinja2": "generates output from templates",
    "rich": "creates styled terminal output with colors and tables",
    "cryptography": "handles encryption and security",
    "jwt": "handles login tokens (JWT)",
    "passlib": "hashes and verifies passwords",
    "smtplib": "sends emails",
    "boto3": "connects to Amazon Web Services (AWS)",
    "stripe": "handles Stripe payments",
    "pydicom": "reads and writes medical imaging (DICOM) files",
    "pynetdicom": "communicates with medical imaging systems over a network",
    "hl7": "processes healthcare messages (HL7 format)",
    "fhir": "works with healthcare data (FHIR standard)",
    "mcp": "exposes tools for AI assistants via MCP protocol",
    "openai": "connects to OpenAI's API",
    "anthropic": "connects to Anthropic's Claude API",
    "selenium": "automates web browsers",
    "beautifulsoup4": "scrapes data from web pages",
    "bs4": "scrapes data from web pages",
    "scrapy": "crawls and scrapes websites",
    "pandas": "processes and analyzes tabular data",
    "numpy": "does numerical/math computations",
    "matplotlib": "creates charts and graphs",
    "pillow": "processes images",
    "PIL": "processes images",
    "socket": "handles low-level network connections",
    "sqlite3": "reads/writes a local SQLite database",
    "email": "constructs email messages",
    "hashlib": "creates hashes for data integrity or security",
    "secrets": "generates secure random values",
    "os": "interacts with the operating system",
    "pathlib": "works with file paths",
    "re": "searches text using regular expressions",
    "ast": "inspects Python code structure programmatically",
    "dataclasses": "defines structured data containers",
    "abc": "defines abstract base classes (blueprints for other classes)",
}

# Maps class base names to plain-English descriptions
_CLASS_BASE_HINTS: dict[str, str] = {
    "ABC": "a blueprint that other classes must follow",
    "BaseModel": "a data structure with built-in validation (Pydantic)",
    "Model": "represents a database table",
    "TestCase": "a group of related tests",
    "Exception": "a custom error type",
    "Enum": "a fixed set of named choices",
    "Protocol": "a contract that other classes can implement",
    "TypedDict": "a dictionary with a defined structure",
}

# Maps decorator names to what they mean
_DECORATOR_HINTS: dict[str, str] = {
    "app.route": "responds to web requests at a specific URL",
    "app.get": "responds to GET requests (reading data)",
    "app.post": "responds to POST requests (submitting data)",
    "app.put": "responds to PUT requests (updating data)",
    "app.delete": "responds to DELETE requests (removing data)",
    "router.get": "responds to GET requests (reading data)",
    "router.post": "responds to POST requests (submitting data)",
    "main.command": "a command you can run in the terminal",
    "click.command": "a command you can run in the terminal",
    "click.group": "a group of related terminal commands",
    "property": "acts like an attribute but computes its value",
    "staticmethod": "a utility that doesn't need object state",
    "classmethod": "works on the class itself, not an instance",
    "abstractmethod": "must be implemented by child classes",
    "pytest.fixture": "sets up test data or resources",
    "pytest.mark.parametrize": "runs the same test with different inputs",
    "register_scanner": "registers this as a scanner plugin",
    "dataclass": "a structured data container",
    "cached_property": "computes once, then remembers the result",
}

# Maps filename patterns to what the file is for
_FILENAME_HINTS: list[tuple[str, str]] = [
    ("__init__", "Makes this folder a Python package (usually empty or re-exports)"),
    ("__main__", "The starting point when you run this package directly"),
    ("conftest", "Shared test setup — fixtures and helpers used across test files"),
    ("test_", "Automated tests that verify "),  # suffix added dynamically
    ("_test", "Automated tests"),
    ("cli", "Defines the commands you can run in your terminal"),
    ("config", "Stores settings and configuration values"),
    ("settings", "Stores settings and configuration values"),
    ("models", "Defines the data structures used throughout the project"),
    ("schemas", "Defines what valid data looks like (validation rules)"),
    ("routes", "Maps web URLs to the code that handles them"),
    ("views", "Contains the logic that runs when a web page is requested"),
    ("middleware", "Code that runs before/after every request (auth, logging, etc.)"),
    ("utils", "Reusable helper functions shared across the project"),
    ("helpers", "Reusable helper functions shared across the project"),
    ("constants", "Fixed values that don't change (limits, labels, defaults)"),
    ("exceptions", "Custom error types specific to this project"),
    ("migrations", "Changes to the database structure over time"),
    ("tasks", "Background jobs that run outside the main request cycle"),
    ("serializers", "Converts data between formats (e.g., Python objects to JSON)"),
    ("admin", "Configuration for the admin dashboard"),
    ("auth", "Handles login, logout, and identity verification"),
    ("permissions", "Controls who can access what"),
    ("validators", "Checks that input data meets requirements before processing"),
    ("factories", "Creates test data for automated tests"),
    ("fixtures", "Pre-built test data and setup"),
    ("setup", "Project installation and packaging configuration"),
    ("registry", "Keeps track of available plugins or components"),
    ("runner", "Coordinates the main workflow — calls other modules in order"),
    ("engine", "The core processing logic that does the main work"),
    ("scanner", "Inspects code or data and reports what it finds"),
    ("analyzer", "Examines code or data to extract information"),
    ("reporter", "Formats results into readable output (terminal, files, etc.)"),
    ("parser", "Reads raw input and converts it into structured data"),
    ("walker", "Walks through directories finding files to process"),
    ("license", "Verifies that the user has a valid license key"),
    ("scoring", "Calculates scores or grades from analysis results"),
    ("server", "Runs a service that listens for and responds to requests"),
    ("client", "Connects to and communicates with an external service"),
    ("connection", "Manages connections to external systems"),
    ("formatter", "Converts data into a specific display format"),
    ("formatting", "Converts data into a specific display format"),
    ("generator", "Produces output (code, documents, reports) from templates or rules"),
    ("mapper", "Translates data from one format or structure to another"),
    ("converter", "Translates data from one format to another"),
    ("guard", "Protects against invalid or dangerous operations"),
    ("handler", "Processes specific types of events or requests"),
    ("dispatcher", "Routes incoming requests to the right handler"),
    ("factory", "Creates and configures objects based on parameters"),
    ("decorator", "Adds behavior to functions or classes"),
    ("base", "Foundation class that other classes build on"),
    ("abstract", "Blueprint that child classes must implement"),
    ("mock", "Fake version of something used in testing"),
    ("fake", "Fake version of something used in testing"),
    ("stub", "Simplified stand-in used in testing"),
    ("backend", "The behind-the-scenes service that does the actual work"),
    ("frontend", "The user-facing part of the application"),
    ("api", "Defines the interface for external communication"),
    ("endpoint", "A specific URL or path that accepts requests"),
    ("service", "Business logic that orchestrates multiple operations"),
    ("repository", "Abstracts database access behind a clean interface"),
    ("cache", "Stores frequently used data for faster access"),
    ("queue", "Manages items waiting to be processed"),
    ("worker", "Processes items from a queue in the background"),
    ("scheduler", "Triggers actions at specific times or intervals"),
    ("cron", "Triggers actions on a schedule"),
    ("webhook", "Receives notifications from external services"),
    ("callback", "Code that runs in response to an event"),
    ("listener", "Waits for and responds to events"),
    ("watcher", "Monitors for changes and triggers actions"),
    ("monitor", "Tracks system health or performance"),
    ("logger", "Records events and errors for debugging"),
    ("audit", "Tracks who did what and when"),
    ("notification", "Sends alerts to users or systems"),
    ("email", "Handles sending or receiving emails"),
    ("template", "A reusable pattern for generating output"),
    ("theme", "Visual styling and appearance settings"),
    ("style", "Visual styling and appearance settings"),
    ("layout", "Defines how content is arranged on screen"),
    ("component", "A reusable building block of the UI"),
    ("widget", "A self-contained UI element"),
    ("page", "A full screen or view in the application"),
    ("form", "Handles user input collection and validation"),
    ("table", "Displays data in rows and columns"),
    ("chart", "Displays data as a visual graph"),
    ("dashboard", "Overview screen showing key metrics"),
    ("dictionary", "Reference data — lookup tables and definitions"),
    ("mapping", "Reference data that translates between systems or formats"),
    ("knowledge", "Reference data and domain expertise"),
]


def _filename_matches(stem: str, pattern: str) -> bool:
    """Check if a filename stem matches a pattern using word boundaries.

    Prevents 'cli' from matching 'client', 'client_pool', etc.
    Patterns starting with _ or __ (like __init__, test_) use prefix/suffix matching.
    Other patterns must match the full stem or appear as a word boundary segment.
    """
    # Exact match always works
    if stem == pattern:
        return True
    # Prefix patterns (test_, __init__, __main__)
    if pattern.startswith("_") or pattern.endswith("_"):
        return stem.startswith(pattern) or stem.endswith(pattern)
    # Word-boundary matching: pattern must appear as a complete segment
    # separated by underscores, hyphens, or at start/end of string
    segments = stem.replace("-", "_").split("_")
    return pattern in segments


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

    Strategy: build the most specific description possible by combining
    filename hints, import analysis, and function name analysis.
    Prioritizes saying what the file DOES over what libraries it USES.
    """
    # Try filename first — most reliable signal
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem_lower = stem.lower()

    filename_hint = ""
    for pattern, desc in _FILENAME_HINTS:
        if _filename_matches(stem_lower, pattern):
            # Special case: test files get the subject appended
            if pattern == "test_" and len(stem) > 5:
                subject = stem[5:].replace("_", " ")
                filename_hint = f"Tests that verify {subject} works correctly"
            else:
                filename_hint = desc
            break

    # Analyze function names for intent
    func_hint = _summarize_functions(function_names)

    # Analyze imports for context (skip noisy/common ones)
    import_hint = _summarize_imports(imports)

    # Analyze class names
    class_hint = _summarize_classes(class_names, class_bases)

    # Build the summary from best available signals
    if filename_hint and func_hint:
        return f"{filename_hint}. {func_hint}"
    if filename_hint:
        return filename_hint
    if class_hint and func_hint:
        return f"{class_hint}. {func_hint}"
    if class_hint:
        return class_hint
    if func_hint:
        if import_hint:
            return f"{func_hint} ({import_hint})"
        return func_hint
    if import_hint:
        return import_hint
    if has_main_guard:
        return "Can be run directly as a script"
    if function_names:
        return _describe_function_collection(function_names)
    if class_names:
        return f"Defines {', '.join(class_names)}"
    return "Supporting code"


def _summarize_functions(names: list[str]) -> str:
    """Describe what a collection of functions does based on their names."""
    if not names:
        return ""

    public = [n for n in names if not n.startswith("_")]
    if not public:
        return ""

    # Look for dominant verb patterns
    verbs: dict[str, list[str]] = {}
    for name in public:
        prefix = name.split("_")[0] if "_" in name else ""
        if prefix in ("get", "fetch", "load", "read", "find", "list", "search", "query"):
            verbs.setdefault("retrieves", []).append(name)
        elif prefix in ("set", "update", "save", "write", "store", "put"):
            verbs.setdefault("updates", []).append(name)
        elif prefix in ("create", "make", "build", "generate", "add", "new"):
            verbs.setdefault("creates", []).append(name)
        elif prefix in ("delete", "remove", "drop", "clear", "destroy"):
            verbs.setdefault("removes", []).append(name)
        elif prefix in ("check", "validate", "verify", "is", "has", "can"):
            verbs.setdefault("validates", []).append(name)
        elif prefix in ("parse", "decode", "extract", "split"):
            verbs.setdefault("parses", []).append(name)
        elif prefix in ("format", "render", "display", "show", "print"):
            verbs.setdefault("displays", []).append(name)
        elif prefix in ("send", "post", "push", "emit", "publish", "notify"):
            verbs.setdefault("sends", []).append(name)
        elif prefix in ("handle", "process", "run", "execute", "dispatch"):
            verbs.setdefault("processes", []).append(name)
        elif prefix in ("convert", "transform", "map", "translate"):
            verbs.setdefault("converts", []).append(name)
        elif prefix in ("init", "setup", "configure", "register"):
            verbs.setdefault("sets up", []).append(name)
        elif prefix in ("test",):
            verbs.setdefault("tests", []).append(name)
        elif prefix in ("log", "record", "track", "audit"):
            verbs.setdefault("records", []).append(name)
        elif prefix in ("connect", "open", "close", "disconnect"):
            verbs.setdefault("manages connections for", []).append(name)
        elif prefix in ("encrypt", "decrypt", "hash", "sign"):
            verbs.setdefault("handles encryption for", []).append(name)
        elif prefix in ("explain", "describe", "summarize", "document"):
            verbs.setdefault("explains", []).append(name)
        elif prefix in ("lookup", "resolve", "find"):
            verbs.setdefault("looks up", []).append(name)

    if verbs:
        # Describe the dominant action
        dominant = max(verbs.items(), key=lambda x: len(x[1]))
        action = dominant[0]
        subjects = [n.split("_", 1)[1].replace("_", " ") if "_" in n else n for n in dominant[1][:3]]
        if len(subjects) == 1:
            return f"{action.capitalize()} {subjects[0]}"
        if len(dominant[1]) > 3:
            return f"{action.capitalize()} {', '.join(subjects)}, and more"
        return f"{action.capitalize()} {', '.join(subjects)}"

    return ""


def _describe_function_collection(names: list[str]) -> str:
    """Last-resort description based on function names."""
    public = [n for n in names if not n.startswith("_")]
    if not public:
        public = names

    domain = _guess_domain(public)
    if len(public) == 1:
        readable = public[0].replace("_", " ")
        return f"Handles {readable}"
    if len(public) <= 3:
        readable = [n.replace("_", " ") for n in public]
        return f"Handles {', '.join(readable)}"

    return f"Contains {len(public)} functions for {domain}"


def _guess_domain(names: list[str]) -> str:
    """Guess the domain from a list of function names."""
    joined = " ".join(n.lower() for n in names)
    if any(w in joined for w in ["dicom", "tag", "pacs", "imaging"]):
        return "medical imaging operations"
    if any(w in joined for w in ["hl7", "segment", "message", "ack"]):
        return "healthcare message processing"
    if any(w in joined for w in ["fhir", "resource", "bundle"]):
        return "healthcare data conversion"
    if any(w in joined for w in ["mirth", "channel"]):
        return "integration engine management"
    if any(w in joined for w in ["format", "render", "display"]):
        return "formatting and display"
    if any(w in joined for w in ["parse", "read", "decode"]):
        return "reading and parsing data"
    if any(w in joined for w in ["scan", "check", "validate"]):
        return "analysis and validation"
    if any(w in joined for w in ["auth", "login", "token"]):
        return "authentication"
    if any(w in joined for w in ["user", "account", "profile"]):
        return "user management"
    if any(w in joined for w in ["file", "path", "dir"]):
        return "file operations"
    if any(w in joined for w in ["http", "request", "response", "api"]):
        return "HTTP/API operations"
    if any(w in joined for w in ["db", "query", "table", "record"]):
        return "database operations"
    return "various operations"


def _summarize_imports(imports: list[str]) -> str:
    """Pick the most informative import to describe what the file uses."""
    # Skip noisy/ubiquitous imports
    skip = {"os", "sys", "pathlib", "typing", "dataclasses", "re",
            "json", "logging", "abc", "ast", "collections", "functools",
            "datetime", "enum", "contextlib", "copy", "math", "hashlib",
            "time", "textwrap", "itertools", "__future__"}

    meaningful: list[str] = []
    for imp in imports:
        top = imp.split(".")[0]
        if top in skip:
            continue
        if top in _IMPORT_HINTS:
            meaningful.append(_IMPORT_HINTS[top])

    if not meaningful:
        return ""

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for m in meaningful:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    if len(unique) == 1:
        return unique[0].capitalize()
    return f"{unique[0].capitalize()} and {unique[1]}"


def _summarize_classes(names: list[str], bases: list[list[str]]) -> str:
    """Describe classes in the file using readable language."""
    if not names:
        return ""

    hints: list[str] = []
    for i, name in enumerate(names):
        readable = _class_name_to_words(name)
        if i < len(bases) and bases[i]:
            for base in bases[i]:
                base_name = base.rsplit(".", 1)[-1]
                if base_name in _CLASS_BASE_HINTS:
                    hints.append(f"the {readable} {_CLASS_BASE_HINTS[base_name]}")
                    break
            else:
                hints.append(f"the {readable}" if readable != name.lower() else name)
        else:
            hints.append(f"the {readable}" if readable != name.lower() else name)

    if len(hints) == 1:
        return f"Defines {hints[0]}"
    return f"Defines {', '.join(hints[:3])}"


def infer_function_description(
    name: str,
    decorators: list[str],
    docstring: str | None,
    calls: list[str],
) -> str:
    """Infer a plain-English description for a function.

    Priority: docstring > decorator > naming convention > fallback.
    """
    if docstring:
        first_line = docstring.split("\n")[0].strip()
        if first_line:
            return first_line

    # Check decorators
    for dec in decorators:
        if dec in _DECORATOR_HINTS:
            return _DECORATOR_HINTS[dec].capitalize()

    # Naming conventions — plain English
    if name.startswith("test_"):
        subject = name[5:].replace("_", " ")
        return f"Verifies that {subject} works correctly"
    if name.startswith("_") and name != "__init__":
        # Try to describe private helpers too
        inner = name.lstrip("_")
        inner_desc = _describe_name(inner)
        if inner_desc:
            return f"{inner_desc} (internal)"
        return "Internal helper — supports the functions above"

    desc = _describe_name(name)
    if desc:
        return desc

    if name == "__init__":
        return "Sets up a new instance with its initial values"
    if name == "__str__" or name == "__repr__":
        return "Controls how this object looks when printed"
    if name == "__enter__":
        return "Runs when entering a 'with' block"
    if name == "__exit__":
        return "Runs when leaving a 'with' block (cleanup)"
    if name == "__call__":
        return "Makes this object callable like a function"
    if name == "__eq__":
        return "Defines how two objects are compared for equality"
    if name == "__hash__":
        return "Generates a hash value for use in sets and dicts"
    if name == "__len__":
        return "Returns the length/size of this object"
    if name == "__iter__":
        return "Allows looping over this object"
    if name == "__getitem__":
        return "Allows accessing items with bracket notation"

    return ""


def _describe_name(name: str) -> str:
    """Describe a function based on its name pattern."""
    if "_" not in name:
        return ""

    prefix, _, suffix = name.partition("_")
    subject = suffix.replace("_", " ")

    descriptions: dict[str, str] = {
        "get": f"Retrieves {subject}",
        "fetch": f"Fetches {subject} from an external source",
        "load": f"Loads {subject} into memory",
        "read": f"Reads {subject}",
        "find": f"Searches for {subject}",
        "list": f"Returns a list of {subject}",
        "search": f"Searches for matching {subject}",
        "query": f"Queries for {subject}",
        "set": f"Sets the value of {subject}",
        "update": f"Updates {subject} with new values",
        "save": f"Saves {subject} to storage",
        "write": f"Writes {subject} to a file or output",
        "store": f"Stores {subject} for later use",
        "put": f"Sends {subject} to a destination",
        "create": f"Creates a new {subject}",
        "make": f"Builds {subject}",
        "build": f"Constructs {subject} step by step",
        "generate": f"Generates {subject} from inputs or templates",
        "add": f"Adds {subject}",
        "new": f"Creates a new {subject}",
        "delete": f"Deletes {subject}",
        "remove": f"Removes {subject}",
        "drop": f"Drops {subject}",
        "clear": f"Clears all {subject}",
        "destroy": f"Permanently destroys {subject}",
        "check": f"Checks {subject}",
        "validate": f"Validates that {subject} meets requirements",
        "verify": f"Verifies {subject} is correct",
        "is": f"Checks whether {subject} is true",
        "has": f"Checks whether {subject} exists",
        "can": f"Checks whether {subject} is allowed",
        "ensure": f"Makes sure {subject} is ready",
        "require": f"Ensures {subject} is present or fails",
        "parse": f"Reads raw {subject} and converts it to structured data",
        "decode": f"Decodes {subject} from an encoded format",
        "extract": f"Pulls {subject} out of a larger structure",
        "split": f"Splits {subject} into parts",
        "format": f"Formats {subject} for display",
        "render": f"Renders {subject} into visual output",
        "display": f"Displays {subject}",
        "show": f"Shows {subject}",
        "print": f"Prints {subject} to output",
        "send": f"Sends {subject} to a destination",
        "post": f"Posts {subject}",
        "push": f"Pushes {subject} to a queue or service",
        "emit": f"Emits {subject} as an event",
        "publish": f"Publishes {subject}",
        "notify": f"Sends a notification about {subject}",
        "handle": f"Handles {subject} when it occurs",
        "process": f"Processes {subject} through the pipeline",
        "run": f"Runs {subject}",
        "execute": f"Executes {subject}",
        "dispatch": f"Routes {subject} to the right handler",
        "convert": f"Converts {subject} from one format to another",
        "transform": f"Transforms {subject}",
        "map": f"Maps {subject} to a new structure",
        "translate": f"Translates {subject} between formats",
        "init": f"Initializes {subject}",
        "setup": f"Sets up {subject}",
        "configure": f"Configures {subject} with settings",
        "register": f"Registers {subject} so the system knows about it",
        "connect": f"Opens a connection to {subject}",
        "disconnect": f"Closes the connection to {subject}",
        "open": f"Opens {subject}",
        "close": f"Closes {subject}",
        "start": f"Starts {subject}",
        "stop": f"Stops {subject}",
        "reset": f"Resets {subject} to its default state",
        "clean": f"Cleans up {subject}",
        "cleanup": f"Cleans up {subject} after use",
        "log": f"Records {subject} in the log",
        "record": f"Records {subject}",
        "track": f"Tracks {subject} over time",
        "count": f"Counts {subject}",
        "calculate": f"Calculates {subject}",
        "compute": f"Computes {subject}",
        "sort": f"Sorts {subject}",
        "filter": f"Filters {subject} based on criteria",
        "merge": f"Merges multiple {subject} together",
        "combine": f"Combines {subject}",
        "compare": f"Compares {subject}",
        "match": f"Finds matches in {subject}",
        "resolve": f"Resolves {subject} to a concrete value",
        "lookup": f"Looks up {subject} in a reference table",
        "normalize": f"Normalizes {subject} into a standard format",
        "sanitize": f"Cleans {subject} to remove unsafe content",
        "escape": f"Escapes special characters in {subject}",
        "encode": f"Encodes {subject} into a specific format",
        "hash": f"Creates a hash of {subject}",
        "encrypt": f"Encrypts {subject}",
        "decrypt": f"Decrypts {subject}",
        "wrap": f"Wraps {subject} with additional behavior",
        "unwrap": f"Unwraps {subject} to get the inner value",
        "explain": f"Explains {subject} in human-readable terms",
        "describe": f"Describes {subject}",
        "summarize": f"Summarizes {subject}",
        "infer": f"Infers {subject} from context",
        "detect": f"Detects {subject}",
        "scan": f"Scans for {subject}",
        "analyze": f"Analyzes {subject}",
        "inspect": f"Inspects {subject} in detail",
        "walk": f"Walks through {subject} item by item",
        "iterate": f"Iterates over {subject}",
        "collect": f"Collects {subject} from multiple sources",
        "gather": f"Gathers {subject} together",
        "aggregate": f"Aggregates {subject} into a summary",
        "score": f"Scores {subject}",
        "grade": f"Grades {subject}",
        "rank": f"Ranks {subject}",
        "rate": f"Rates {subject}",
        "apply": f"Applies {subject}",
        "install": f"Installs {subject}",
        "uninstall": f"Uninstalls {subject}",
        "enable": f"Enables {subject}",
        "disable": f"Disables {subject}",
        "activate": f"Activates {subject}",
        "deactivate": f"Deactivates {subject}",
        "import": f"Imports {subject}",
        "export": f"Exports {subject}",
        "download": f"Downloads {subject}",
        "upload": f"Uploads {subject}",
        "sync": f"Syncs {subject} between sources",
        "backup": f"Backs up {subject}",
        "restore": f"Restores {subject} from backup",
        "retry": f"Retries {subject} after failure",
        "recover": f"Recovers {subject} after an error",
        "rollback": f"Rolls back {subject} to a previous state",
        "migrate": f"Migrates {subject} to a new format or location",
    }

    if prefix in descriptions:
        return descriptions[prefix]
    return ""


def infer_class_description(
    name: str,
    bases: list[str],
    docstring: str | None,
) -> str:
    """Infer a plain-English description for a class."""
    if docstring:
        first_line = docstring.split("\n")[0].strip()
        if first_line:
            return first_line

    for base in bases:
        base_name = base.rsplit(".", 1)[-1]
        if base_name in _CLASS_BASE_HINTS:
            return f"{name} — {_CLASS_BASE_HINTS[base_name]}"

    # Name-based inference
    name_lower = name.lower()
    words = _class_name_to_words(name)
    if "error" in name_lower or "exception" in name_lower:
        return f"A custom error type raised when {words} fails"
    if "config" in name_lower or "settings" in name_lower:
        return f"Holds configuration settings for {words}"
    if "handler" in name_lower:
        return f"Handles {words} events or requests"
    if "manager" in name_lower:
        return f"Manages the lifecycle of {words}"
    if "factory" in name_lower:
        return f"Creates and configures {words} instances"
    if "client" in name_lower:
        return f"Talks to the {words} service"
    if "server" in name_lower:
        return f"Runs the {words} service"
    if "scanner" in name_lower:
        return f"Scans code for {words} issues and reports what it finds"
    if "analyzer" in name_lower:
        return f"Analyzes {words} and extracts useful information"
    if "reporter" in name_lower:
        return f"Formats {words} results into readable output"
    if "parser" in name_lower:
        return f"Reads raw {words} data and makes sense of it"
    if "validator" in name_lower:
        return f"Checks that {words} meets requirements"
    if "builder" in name_lower:
        return f"Builds {words} step by step"
    if "wrapper" in name_lower:
        return f"Wraps {words} with extra functionality"
    if "adapter" in name_lower:
        return f"Adapts {words} to work with a different interface"
    if "converter" in name_lower:
        return f"Converts {words} from one format to another"
    if "mapper" in name_lower:
        return f"Maps {words} between different structures"
    if "provider" in name_lower:
        return f"Supplies {words} to other parts of the system"
    if "controller" in name_lower:
        return f"Controls the flow of {words}"
    if "middleware" in name_lower:
        return f"Sits between requests and responses, handling {words}"
    if "plugin" in name_lower:
        return f"An add-on that extends {words} functionality"
    if "mixin" in name_lower:
        return f"Adds {words} capabilities to other classes"
    if "interface" in name_lower:
        return f"Defines the contract for {words}"
    if "test" in name_lower:
        return f"Tests for {words}"
    if "info" in name_lower:
        return f"Holds information about {words}"
    if "result" in name_lower:
        return f"Contains the results of {words}"
    if "response" in name_lower:
        return f"Represents a response from {words}"
    if "request" in name_lower:
        return f"Represents a request to {words}"
    if "context" in name_lower:
        return f"Carries shared state for {words}"
    if "state" in name_lower:
        return f"Tracks the current state of {words}"
    if "event" in name_lower:
        return f"Represents a {words} event"
    if "command" in name_lower:
        return f"Represents a {words} command to execute"
    if "task" in name_lower:
        return f"A unit of work for {words}"
    if "job" in name_lower:
        return f"A background job that handles {words}"
    if "record" in name_lower:
        return f"A data record for {words}"
    if "entry" in name_lower:
        return f"A single entry in {words}"
    if "item" in name_lower:
        return f"A single item in {words}"
    if "node" in name_lower:
        return f"A node in the {words} structure"
    if "base" in name_lower:
        return f"The foundation that other {words} classes build on"

    return ""


def _class_name_to_words(name: str) -> str:
    """Convert CamelCase to readable words, stripping common suffixes."""
    import re
    # Remove common suffixes
    for suffix in ("Handler", "Manager", "Factory", "Client", "Server",
                   "Error", "Exception", "Config", "Settings", "Test"):
        if name.endswith(suffix) and name != suffix:
            name = name[: -len(suffix)]
            break
    # Split CamelCase
    words = re.sub(r"([A-Z])", r" \1", name).strip().lower()
    return words
