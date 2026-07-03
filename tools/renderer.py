"""
Markdown renderer using Python-Markdown + PyMdown FancyLists.
"""

import markdown
# this was used when all the websites were under public_html/en/v2/{en,fr,hr} for testing
# now they are under public_html/{en,fr,hr}
# from resolve_images import resolve_images

def markdown_to_html(md: str, base_path: str = None) -> str:
    # md = resolve_images(md, base_path)
    html = markdown.markdown(
        md,
        extensions=[
            "pymdownx.fancylists",
            "pymdownx.saneheaders",
            "nl2br"
        ],
        extension_configs={
            "pymdownx.fancylists": {
                "inject_style": True,
                "inject_class": True,
            }
        },
        output_format="html5",
    )
    return html

def format_markdown(md: str) -> str:
    """
    Format Markdown text.
    """
    md = md.strip()
    lines = md.splitlines()
    lines = [line.rstrip() for line in lines]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    md = "\n\n".join(lines)
    md = md.rstrip() + "\n"
    
    max_line_length = 80
    wrapped_lines = []
    
    for line in md.splitlines():
        if len(line) <= max_line_length:
            wrapped_lines.append(line)
        else:
            # wrap the line
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= max_line_length:
                    current_line += (word + " ")
                else:
                    wrapped_lines.append(current_line.rstrip())
                    current_line = word + " "
            if current_line:
                wrapped_lines.append(current_line.rstrip())
    
    return "\n".join(wrapped_lines)
    
    
    
    
    