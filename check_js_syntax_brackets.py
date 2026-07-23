with open('app.js', 'r', encoding='utf-8') as f:
    code = f.read()

open_curly = 0
open_paren = 0
open_bracket = 0

stack = []

lines = code.splitlines()
for i, line in enumerate(lines):
    # Strip comments and strings roughly
    clean_line = ""
    in_str = None
    j = 0
    while j < len(line):
        ch = line[j]
        if in_str:
            if ch == '\\':
                j += 1
            elif ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'", '`'):
                in_str = ch
            elif ch == '/' and j + 1 < len(line) and line[j+1] == '/':
                break # line comment
            else:
                clean_line += ch
        j += 1

    for col, ch in enumerate(clean_line):
        if ch == '{':
            open_curly += 1
            stack.append(('{', i + 1, col + 1))
        elif ch == '}':
            open_curly -= 1
            if stack and stack[-1][0] == '{':
                stack.pop()
            else:
                print(f"UNMATCHED '}}' at line {i+1}, col {col+1}")
        elif ch == '(':
            open_paren += 1
            stack.append(('(', i + 1, col + 1))
        elif ch == ')':
            open_paren -= 1
            if stack and stack[-1][0] == '(':
                stack.pop()
            else:
                print(f"UNMATCHED ')' at line {i+1}, col {col+1}")

print(f"\nTOTAL OPEN '{'{'}': {code.count('{')}, TOTAL CLOSE '{'}'}': {code.count('}')}")
print(f"TOTAL OPEN '(': {code.count('(')}, TOTAL CLOSE ')': {code.count(')')}")

if stack:
    print(f"\nUnclosed elements remaining on stack ({len(stack)}):")
    for item in stack[-15:]:
        print(f"  Unclosed '{item[0]}' opened at line {item[1]}, col {item[2]}")
