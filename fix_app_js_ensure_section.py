with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for idx, line in enumerate(lines):
    line_num = idx + 1
    if line_num == 8192:
        skip = True
        # Insert clean ensureSectionData
        new_lines.append("async function ensureSectionData(name, force = false) {\n")
        new_lines.append("    console.log(`[LAZY LOAD LOG] ensureSectionData called for '${name}'`);\n")
        new_lines.append("    hideSectionSkeleton(name);\n")
        new_lines.append("    if (!state || !state.overview || Object.keys(state.overview).length === 0 || force) {\n")
        new_lines.append("        await loadDashboardFromCache(force);\n")
        new_lines.append("    }\n")
        new_lines.append("    renderSection(name);\n")
        new_lines.append("}\n")
    elif line_num == 8267:
        skip = False
    elif not skip:
        new_lines.append(line)

with open('app.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Successfully updated app.js! New line count: {len(new_lines)}")
