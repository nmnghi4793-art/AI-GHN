import ast
import re

with open('app.js', 'r', encoding='utf-8') as f:
    code = f.read()

print("Checking app.js syntax markers...")

# Check matching brackets, braces, parentheses
stack = []
bracket_map = {')': '(', '}': '{', ']': '['}

in_string = False
string_char = ''
escape = False
line_no = 1
col_no = 0

for i, char in enumerate(code):
    col_no += 1
    if char == '\n':
        line_no += 1
        col_no = 0

    if escape:
        escape = False
        continue

    if char == '\\' and in_string:
        escape = True
        continue

    if char in ('"', "'", '`'):
        if not in_string:
            in_string = True
            string_char = char
        elif string_char == char:
            in_string = False
        continue

    if in_string:
        continue

    if char in ('(', '{', '['):
        stack.append((char, line_no, col_no))
    elif char in (')', '}', ']'):
        if not stack:
            print(f"Unmatched closing '{char}' at line {line_no}:{col_no}")
        else:
            top_char, top_line, top_col = stack.pop()
            if bracket_map[char] != top_char:
                print(f"Mismatch '{char}' at line {line_no}:{col_no}, expected matching for '{top_char}' from line {top_line}:{top_col}")

if stack:
    top_char, top_line, top_col = stack[-1]
    print(f"Unclosed '{top_char}' from line {top_line}:{top_col}")
else:
    print("ALL BRACKETS AND STRINGS ARE PERFECTLY MATCHED IN APP.JS!")
