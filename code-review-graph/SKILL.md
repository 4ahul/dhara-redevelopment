---
name: code-review-graph
description: Use code-review-graph to map the codebase, find dependencies, detect change blast-radiuses, and generate minimal architecture summaries to save LLM context tokens.
---

# Code Review Graph (Token Reduction Workflow)

The `code-review-graph` tool builds a structural map of the codebase using Tree-sitter. This allows you (the AI) to understand the architecture, find dependencies, and see the impact of changes **without reading thousands of lines of raw source code**.

## Core Workflows

### 1. Build or Update the Graph

Before running analysis, ensure the graph is up to date.

*   **Initial Build:** Run this if the graph doesn't exist yet (creates `.crg/` directory).
    ```bash
    python -m code_review_graph build
    ```
*   **Incremental Update:** Run this if files have changed since the last build (very fast).
    ```bash
    python -m code_review_graph update
    ```

### 2. Generate and Read Architectural Summaries (Wiki)

Instead of reading massive source files to understand how a service works, generate structural summaries (wikis). The tool analyzes code clusters ("communities") and outputs highly condensed markdown.

1.  **Generate the Wiki:**
    ```bash
    python -m code_review_graph wiki
    ```
2.  **Read the Summaries:**
    The wiki files are generated in `.crg/wiki/`. Use the `list_directory` tool to see the available community summaries, and `read_file` to read the specific markdown file for the service or component you are interested in. These files contain structural metadata (classes, functions, dependencies) and use a fraction of the tokens of the raw code.

### 3. Analyze Change Impact (Blast Radius)

Before or after making a code change, you can see exactly which files, functions, and tests are affected. This prevents you from needing to read the entire repository to ensure you didn't break anything.

*   **Detect changes since the last commit (HEAD~1):**
    ```bash
    python -m code_review_graph detect-changes
    ```
*   **Detect changes between specific branches/commits:**
    ```bash
    python -m code_review_graph detect-changes --base main
    ```

The output will list the specific callers, dependents, and tests affected by the diff. **Only read the files listed in the blast radius** to verify your changes.

## Best Practices for Token Efficiency

*   **Never `read_file` an entire directory of source code** to understand it. Always run `python -m code_review_graph wiki` and read the `.crg/wiki/` markdown files first.
*   **Always run `update`** after you make a file edit so the graph stays in sync.
*   **Rely on `detect-changes`** to find tests that need updating. If a function is modified, the graph will output exactly which test files call it.
