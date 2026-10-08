from docx import Document

d = Document(r"C:\Users\bonkc\Documents\wound-splat\MAIN DOCUMENT (WOUND-SPLAT) - REVISED.docx")
targets = [
    "Algorithm Implementation",
    "The implemented algorithm connects the web application to a seven-stage reconstruction and measurement pipeline.",
    "Step 1 – Frame Extraction",
    "Multiple Constraints and Trade-off Analysis",
    "Project Development",
    "Testing and Operating Procedure",
    "Formula 1: Processing Time",
    "Tprocess = tcompleted − tstarted",
    "This section outlines the architectural design of the Wound-Splat framework",
    "Wound-Splat follows a client-server architecture organized into four logical layers",
    "This section defines the criteria that will be used to evaluate the Wound-Splat framework",
    "Constraint Definition",
]

for target in targets:
    matches = [p for p in d.paragraphs if p.text.strip() == target or p.text.strip().startswith(target)]
    print("\nTARGET", repr(target), "count", len(matches))
    for p in matches[:3]:
        pf = p.paragraph_format
        print("text=", repr(p.text[:140]))
        print("style=", p.style.name, "align=", p.alignment, "before=", pf.space_before, "after=", pf.space_after,
              "line=", pf.line_spacing, "left=", pf.left_indent, "right=", pf.right_indent,
              "first=", pf.first_line_indent, "keep=", pf.keep_with_next)
        for i, r in enumerate(p.runs):
            print(" run", i, repr(r.text[:80]), "font", r.font.name, "size", r.font.size,
                  "bold", r.bold, "italic", r.italic, "underline", r.underline)

print("\nSTYLES")
for name in ["normal", "Heading 1", "Heading 2", "Heading 3", "Heading 4", "Heading 5"]:
    s = d.styles[name]
    pf = s.paragraph_format
    print(name, "font", s.font.name, "size", s.font.size, "bold", s.font.bold, "italic", s.font.italic,
          "align", pf.alignment, "before", pf.space_before, "after", pf.space_after,
          "line", pf.line_spacing, "first", pf.first_line_indent)
