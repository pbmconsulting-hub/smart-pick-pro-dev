"""Tournament legal content and DFS disclaimer helpers."""

from __future__ import annotations

DFS_DISCLAIMER_LINES = [
    "Skill-based fantasy contest. No purchase necessary for Open Court.",
    "Must be 18+ (21+ in MA, AZ, IA). Not available in WA, ID, MT, HI, NV.",
    "If you or someone you know has a gambling problem, call 1-800-GAMBLER.",
]

TERMS_PAGE_PATH = "pages/21_📄_Terms_of_Service.py"
PRIVACY_PAGE_PATH = "pages/22_🔒_Privacy_Policy.py"


def get_dfs_disclaimer_markdown() -> str:
    lines = "\n".join([f"- {line}" for line in DFS_DISCLAIMER_LINES])
    return (
        "### DFS Legal Disclaimers\n"
        f"{lines}\n\n"
        f"[Terms of Service]({TERMS_PAGE_PATH}) · [Privacy Policy]({PRIVACY_PAGE_PATH})"
    )
