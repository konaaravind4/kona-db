"""
KonaDB Interactive CLI Shell

Provides an interactive REPL for executing SQL commands, managing document
collections, and accessing AI features.

Usage:
    kona                  # in-memory database
    kona mydb.kona        # file-based database
    python -m kona        # same as above
"""

import os
import sys
import readline

import kona


# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
MAGENTA = "\033[35m"


def format_table(rows):
    """Format rows as an ASCII table."""
    if not rows:
        return "Empty set."

    columns = list(rows[0].keys())
    # Calculate column widths
    widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, "NULL"))
            widths[col] = max(widths[col], len(val))

    # Build table
    sep = "+" + "+".join("-" * (widths[col] + 2) for col in columns) + "+"
    header = "|" + "|".join(f" {BOLD}{col:<{widths[col]}}{RESET} " for col in columns) + "|"

    lines = [sep, header, sep]
    for row in rows:
        vals = "|" + "|".join(
            f" {str(row.get(col, 'NULL')):<{widths[col]}} " for col in columns
        ) + "|"
        lines.append(vals)
    lines.append(sep)
    lines.append(f"{DIM}{len(rows)} row(s) in set{RESET}")
    return "\n".join(lines)


def print_help():
    """Print CLI help."""
    help_text = f"""
{BOLD}{CYAN}KonaDB Shell Commands:{RESET}

  {GREEN}SQL Commands:{RESET}
    Type any MySQL-compatible SQL statement ending with ;

  {GREEN}Dot Commands:{RESET}
    {YELLOW}.tables{RESET}              List all tables
    {YELLOW}.collections{RESET}         List all document collections
    {YELLOW}.schema <table>{RESET}      Show table schema (DESCRIBE)
    {YELLOW}.indexes <table>{RESET}     Show indexes for a table
    {YELLOW}.import csv <table> <file>{RESET}   Import CSV into table
    {YELLOW}.import json <table> <file>{RESET}  Import JSON into table
    {YELLOW}.export csv <table> <file>{RESET}   Export table to CSV
    {YELLOW}.export json <table> <file>{RESET}  Export table to JSON

  {GREEN}AI Commands (requires ANTHROPIC_API_KEY):{RESET}
    {YELLOW}.ai ask <question>{RESET}          Ask a question in English
    {YELLOW}.ai optimize <sql>{RESET}          Get query optimization tips
    {YELLOW}.ai design <description>{RESET}    Generate schema from description
    {YELLOW}.ai anomalies <table>{RESET}       Detect data quality issues

  {GREEN}Other:{RESET}
    {YELLOW}.help{RESET}                Show this help
    {YELLOW}.exit{RESET} / {YELLOW}.quit{RESET}        Exit the shell
    {YELLOW}Ctrl+D{RESET}               Exit the shell
"""
    print(help_text)


def handle_dot_command(conn, cmd):
    """Handle dot-commands."""
    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == ".help":
        print_help()
    elif command == ".tables":
        tables = conn.tables
        if tables:
            for t in tables:
                print(f"  {GREEN}{t}{RESET}")
        else:
            print(f"  {DIM}No tables{RESET}")
    elif command == ".collections":
        colls = conn.list_collections()
        if colls:
            for c in colls:
                print(f"  {GREEN}{c}{RESET}")
        else:
            print(f"  {DIM}No collections{RESET}")
    elif command == ".schema":
        if not args:
            print(f"{RED}Usage: .schema <table_name>{RESET}")
            return
        try:
            result = conn.execute(f"DESCRIBE {args}")
            print(format_table(result))
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
    elif command == ".indexes":
        if not args:
            print(f"{RED}Usage: .indexes <table_name>{RESET}")
            return
        try:
            result = conn.execute(f"SHOW INDEXES FROM {args}")
            print(format_table(result))
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
    elif command == ".import":
        _handle_import(conn, args)
    elif command == ".export":
        _handle_export(conn, args)
    elif command == ".ai":
        _handle_ai(conn, args)
    elif command in (".exit", ".quit"):
        conn.close()
        print(f"\n{DIM}Goodbye!{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}Unknown command: {command}. Type .help for help.{RESET}")


def _handle_import(conn, args):
    parts = args.split()
    if len(parts) < 3:
        print(f"{RED}Usage: .import csv|json <table> <file>{RESET}")
        return
    fmt, table, filepath = parts[0], parts[1], parts[2]
    try:
        if fmt == "csv":
            count = conn.import_csv(table, filepath)
        elif fmt == "json":
            count = conn.import_json(table, filepath)
        else:
            print(f"{RED}Unknown format: {fmt}. Use csv or json.{RESET}")
            return
        print(f"{GREEN}{count} row(s) imported into '{table}'{RESET}")
    except Exception as e:
        print(f"{RED}Import error: {e}{RESET}")


def _handle_export(conn, args):
    parts = args.split()
    if len(parts) < 3:
        print(f"{RED}Usage: .export csv|json <table> <file>{RESET}")
        return
    fmt, table, filepath = parts[0], parts[1], parts[2]
    try:
        if fmt == "csv":
            count = conn.export_csv(table, filepath)
        elif fmt == "json":
            count = conn.export_json(table, filepath)
        else:
            print(f"{RED}Unknown format: {fmt}. Use csv or json.{RESET}")
            return
        print(f"{GREEN}{count} row(s) exported to '{filepath}'{RESET}")
    except Exception as e:
        print(f"{RED}Export error: {e}{RESET}")


def _handle_ai(conn, args):
    parts = args.split(None, 1)
    if not parts:
        print(f"{RED}Usage: .ai ask|optimize|design|anomalies <args>{RESET}")
        return
    subcmd = parts[0].lower()
    ai_args = parts[1] if len(parts) > 1 else ""

    try:
        if subcmd == "ask":
            result = conn.ask(ai_args)
            print(f"\n{CYAN}SQL:{RESET} {result.get('sql', 'N/A')}")
            if "error" in result:
                print(f"{RED}Error: {result['error']}{RESET}")
            elif "results" in result:
                print(format_table(result["results"]))
        elif subcmd == "optimize":
            result = conn.optimize(ai_args)
            print(f"\n{CYAN}Recommendations:{RESET}\n{result['recommendations']}")
        elif subcmd == "design":
            result = conn.design_schema(ai_args)
            print(f"\n{CYAN}Generated SQL:{RESET}\n{result['sql']}")
        elif subcmd == "anomalies":
            result = conn.detect_anomalies(ai_args)
            print(f"\n{CYAN}Analysis ({result['rows_analyzed']}/{result['total_rows']} rows):{RESET}")
            print(result["findings"])
        else:
            print(f"{RED}Unknown AI command: {subcmd}{RESET}")
    except RuntimeError as e:
        print(f"{RED}{e}{RESET}")
    except Exception as e:
        print(f"{RED}AI error: {e}{RESET}")


def main():
    """Main entry point for the KonaDB CLI."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else ":memory:"

    print(f"""
{BOLD}{MAGENTA}╔═══════════════════════════════════════╗
║         {CYAN}KonaDB Shell v{kona.__version__}{MAGENTA}          ║
║   MySQL-compatible Database Engine    ║
╚═══════════════════════════════════════╝{RESET}
""")

    if db_path == ":memory:":
        print(f"  {DIM}Mode: In-memory database{RESET}")
    else:
        print(f"  {DIM}Connected to: {db_path}{RESET}")
    print(f"  {DIM}Type .help for commands, .exit to quit{RESET}\n")

    conn = kona.connect(db_path)

    # Setup readline history
    histfile = os.path.expanduser("~/.kona_history")
    try:
        readline.read_history_file(histfile)
    except FileNotFoundError:
        pass

    sql_buffer = []

    while True:
        try:
            prompt = f"{CYAN}kona>{RESET} " if not sql_buffer else f"{DIM}  ...>{RESET} "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye!{RESET}")
            break

        stripped = line.strip()
        if not stripped:
            continue

        # Dot commands
        if not sql_buffer and stripped.startswith("."):
            handle_dot_command(conn, stripped)
            continue

        sql_buffer.append(line)

        # Check if statement is complete (ends with ;)
        full_sql = " ".join(sql_buffer).strip()
        if full_sql.endswith(";"):
            sql_buffer = []
            sql = full_sql.rstrip(";").strip()
            if not sql:
                continue
            try:
                result = conn.execute(sql)
                if result:
                    if isinstance(result, list) and result and isinstance(result[0], dict):
                        if "status" in result[0] and len(result[0]) == 1:
                            print(f"{GREEN}{result[0]['status']}{RESET}")
                        else:
                            print(format_table(result))
                    else:
                        print(result)
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")

    conn.close()
    try:
        readline.write_history_file(histfile)
    except Exception:
        pass


if __name__ == "__main__":
    main()
