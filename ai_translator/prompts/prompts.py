from __future__ import annotations


LD_EXPORT_HEADER = """(* @NESTEDCOMMENTS := 'Yes' *)
(* @PATH := '' *)
(* @OBJECTFLAGS := '0, 8' *)
(* @SYMFILEFLAGS := '2048' *)
PROGRAM PLC_LD_PRG_TR
VAR
END_VAR
(* @END_DECLARATION := '0' *)"""


IL_SYSTEM_PROMPT = """You are a deterministic PLC code translation agent.

Your task is to translate Structured Text (ST) to Instruction List (IL) for CoDeSys 2.3.

Rules:
1. Follow the provided grammar and translation constraints exactly.
2. Preserve the original program semantics.
3. Output plain IL only.
4. Do not add markdown, explanations, comments, or surrounding text.
5. Do not use JMP, JMPC, or any label-based control flow.
6. Translate IF and ELSIF logic using S and R style IL logic.
7. Keep one IL instruction per line.
8. Use IEC-style IL instructions such as LD, LDN, AND, ANDN, OR, ORN, NOT, ST, S, and R when appropriate.
9. Parentheses must be used in IL whenever the source expression contains parentheses; do not remove or simplify source grouping.
10. Respect boolean precedence from the source grammar: NOT > AND > OR.
11. Never echo ST syntax in the output.
12. Forbidden output tokens: IF, THEN, ELSIF, END_IF, :=, ;, SET, RESET, JMPC, JMP.
13. Preserve the source expression semantics exactly.
14. When the source expression contains parentheses, reproduce the same grouping in IL even if the result would be logically equivalent without parentheses.
15. Inside an IL parenthesized operand, do not emit LD or ST. Use only the operand text and AND/OR/ANDN/ORN lines.
16. Do not rewrite `OR (A AND B)` as `OR A` followed by `AND B`; keep the parenthesized block.
17. Do not write `OR NOT X` or `AND NOT X` in IL. Use `ORN X` or `ANDN X`.
18. Inside a parenthesized IL block, do not write `NOT X`. If the first grouped operand is negated, write the operand line first and then a separate `NOT` line.
19. Translate `OR NOT X` exactly as `ORN X`; translate `AND NOT X` exactly as `ANDN X`.
20. Translate `AND NOT (...)` as `ANDN (` followed by the group content; do not put `NOT` after the closing parenthesis.
21. Translate `OR NOT (...)` as `ORN (` followed by the group content; do not put `NOT` after the closing parenthesis.
22. Never output double parenthesis after an IL operator: forbidden forms are `AND ((`, `OR ((`, `ANDN ((`, and `ORN ((`.
23. If the ST source contains redundant nested parentheses like `((P AND Q) OR NOT R)`, flatten only the redundant outer layer and emit one IL parenthesized block.
24. If the right side of `OR` is an AND-expression group, keep it as `OR (` block; do not flatten it into `ORN X` followed by `AND Y`.
25. Because ST precedence is AND before OR, every `OR A AND B` or `OR NOT A AND B` segment is an implicit AND-group and must be emitted as an `OR (` block.
"""


LD_SYSTEM_PROMPT = f"""You are a deterministic PLC code translation agent.

Your task is to translate Structured Text (ST) to Ladder Diagram (LD) export text for CoDeSys 2.3.

Rules:
1. Follow the provided grammar and translation constraints exactly.
2. Preserve the original program semantics.
3. Output a plain CoDeSys 2.3 LD export only.
4. Do not add markdown, explanations, comments, or surrounding text.
5. The output must start with this exact header:
{LD_EXPORT_HEADER}
6. The output must end with END_PROGRAM.
7. Use LD export blocks such as _LD_BODY, _NETWORKS, _NETWORK, _LD_ASSIGN, _LD_CONTACT, _LD_AND, _LD_OR, _EXPRESSION, _POSITIV, _NEGATIV, _OUTPUTS, _OUTPUT, _NO_SET, and _SET.
8. For each direct assignment, create one LD network with a _NO_SET output coil.
9. For IF branches assigning TRUE, create a set network with _OUTPUT, _POSITIV, _SET.
10. For IF branches assigning FALSE, create a reset network with _OUTPUT, _NEGATIV, _SET.
11. One IF with ELSIF must produce two networks: one for IF and one for ELSIF.
12. Count all generated networks and write the exact count in _NETWORKS : N. This number must equal the number of `_NETWORK` blocks below `_NETWORKS`.
13. Preserve dotted identifiers exactly as they appear in ST.
14. Treat TRUE/1 as TRUE and FALSE/0 as FALSE.
15. Never echo ST syntax in the output.
16. Never skip source statements. Every source assignment and every IF/ELSIF branch must become LD network(s).
17. For _LD_AND and _LD_OR, _LD_OPERATOR : N must equal the number of direct operands emitted inside that block.
18. Every network must include the full output section: ENABLELIST : 0, ENABLELIST_END, _OUTPUTS : 1, _OUTPUT, output polarity, coil kind, target variable.
19. Before every ENABLELIST, always close the complete LD expression. The two lines immediately before ENABLELIST must be exactly _EXPRESSION and _POSITIV.
20. After _OUTPUT, always emit output polarity. For direct assignments, use _POSITIV before _NO_SET.
21. Do not output `_NETWORKS` until all networks have been planned and counted.
22. Do not split one direct assignment into multiple networks.
23. Do not merge IF/ELSIF branches into one network; each branch is one network.
"""


def build_messages(
    source_code: str,
    grammar_text: str,
    target_language: str,
) -> list[dict[str, str]]:
    target = target_language.upper()
    return [
        {"role": "system", "content": build_system_prompt(target)},
        {
            "role": "user",
            "content": build_translation_prompt(
                source_code=source_code,
                grammar_text=grammar_text,
                target_language=target,
            ),
        },
    ]


def build_system_prompt(target_language: str) -> str:
    if target_language == "IL":
        return IL_SYSTEM_PROMPT
    if target_language == "LD":
        return LD_SYSTEM_PROMPT
    raise ValueError(f"Unsupported target language: {target_language}")


def build_translation_prompt(
    source_code: str,
    grammar_text: str,
    target_language: str,
) -> str:
    if target_language == "IL":
        return build_il_translation_prompt(source_code, grammar_text)
    if target_language == "LD":
        return build_ld_translation_prompt(source_code, grammar_text)
    raise ValueError(f"Unsupported target language: {target_language}")


def build_il_translation_prompt(source_code: str, grammar_text: str) -> str:
    return f"""Translate the following source program from ST to IL for CoDeSys 2.3.

Source grammar:
{grammar_text}

Translation requirements:
- The source program follows the supplied grammar.
- The source language contains assignments and IF / ELSIF / END_IF statements only.
- Expressions are boolean expressions built from identifiers, TRUE, FALSE, 1, 0, parentheses, NOT, AND, and OR.
- For assignments, evaluate the expression and store the final accumulator value with ST <identifier>.
- Do not generate any jumps or labels.
- For IF and ELSIF translation, use S / R based IL logic instead of control-flow jumps.
- For ELSIF blocks, preserve the branch order exactly.
- Preserve dotted identifiers exactly as they appear in ST.
- Treat 1 as TRUE and 0 as FALSE when generating IL.
- Use LDN, ANDN, ORN for direct negated identifiers.
- Translate `OR NOT X` as `ORN X`, never as `OR NOT X`.
- Translate `AND NOT X` as `ANDN X`, never as `AND NOT X`.
- Translate `AND NOT (Expr)` as `ANDN (` followed by the parenthesized expression body and a closing `)`.
- Translate `OR NOT (Expr)` as `ORN (` followed by the parenthesized expression body and a closing `)`.
- Never output `OR NOT (` or `AND NOT (`. Use `ORN (` or `ANDN (` instead.
- Never place `NOT` after a closing `)` to negate only a right-hand group. Use `ANDN (` or `ORN (` instead.
- Never output `AND ((`, `OR ((`, `ANDN ((`, or `ORN ((`. CoDeSys 2.3 IL does not accept a double opening parenthesis directly after an IL operator.
- If the ST source has redundant nested parentheses, for example `((P AND Q) OR NOT R)`, remove only the redundant outer parenthesis level and keep one IL block: `AND (P`, then the group body, then `)`.
- Preserve the exact source operands. Never replace a source identifier with a different identifier.
- Preserve grouping from the source expression. Do not flatten, remove, or simplify parenthesized expressions, even when operator precedence would make the expression logically equivalent.
- For a direct assignment `Y := Expr;`, output exactly one expression followed by `ST Y`.
- Start an assignment expression with `LD <leftmost operand>` or `LDN <operand>` if the expression starts with `NOT`.
- For a binary operation with a parenthesized right side, emit `AND (` or `OR (` and put the grouped expression inside that block. Never rewrite `OR (A AND B)` as `OR A` followed by `AND B`.
- If the right side of `OR` is a grouped AND-expression, keep the whole right side as an `OR (` block. Example: `(A AND B) OR (NOT C AND D)` must use `OR (C`, then `NOT`, then `AND D`, then `)`.
- ST precedence creates implicit AND-groups after OR. Translate `X OR Y AND Z` as `LD X`, then `OR (Y`, then `AND Z`, then `)`. Never translate it as `LD X`, then `OR Y`, then `AND Z`.
- Translate `X OR NOT Y AND NOT Z` as `LD X`, then `OR (Y`, then `NOT`, then `ANDN Z`, then `)`. Never translate it as `LD X`, then `ORN Y`, then `ANDN Z`.
- If several OR-separated terms contain AND, each AND-term after OR must become its own `OR (` block.
- Inside a parenthesized IL block, never emit `LD`, `LDN`, `ST`, `S`, or `R`.
- Inside parentheses, start with the first operand text, for example `AND (B`, not `AND (LD B`.
- Inside parentheses, never write `NOT X` as one line. For a negated first operand, write the operand and then a separate `NOT` line.
- Example: ST group `(NOT SysOn OR UTS)` must be IL block `AND (SysOn`, then `NOT`, then `OR UTS`, then `)`.
- Inside parentheses, translate `OR NOT X` as `ORN X`, not as `OR X` followed by `NOT`.
- Inside parentheses, translate `AND NOT X` as `ANDN X`, not as `AND X` followed by `NOT`.
- A standalone `NOT` inside parentheses is only allowed immediately after the first operand of that parenthesized group, for cases like `(NOT X OR Y)`.
- Close every opened parenthesis using a standalone `)` line.
- Do not invent extra NOT conditions for ELSIF unless they are strictly required for correctness.
- If an ELSIF branch is already mutually exclusive from a previous branch by the source conditions, translate the ELSIF branch directly.
- Never output ST keywords or ST punctuation in the answer.
- Never output any line containing IF, THEN, ELSIF, END_IF, :=, or ;.
- Every non-empty output line must begin with exactly one IL token from this set: LD, LDN, AND, ANDN, OR, ORN, NOT, ST, S, R, or be a standalone `)` line used to close a parenthesized IL block.
- For ST writes use exactly ST <identifier>.
- For set/reset actions use exactly S <identifier> and R <identifier>.
- Never write ST <identifier> := <value>.
- Never write SET or RESET.
- Final IL self-check before output: every source parenthesized group must have a matching IL parenthesized block; no output line may contain `OR NOT`, `AND NOT`, `OR LDN`, `AND LDN`, or `NOT <identifier>`; no output line may contain `AND ((`, `OR ((`, `ANDN ((`, or `ORN ((`; no standalone `NOT` may appear immediately after a `)` line; every assignment must end with exactly one `ST target`; every IF TRUE/FALSE write must use `S target` or `R target`.
- Generate only the translated IL program.

Reference examples:
ST:
Pmp := TS AND ((SysOn AND TP3) OR SBSink);
IL:
LD TS
AND (SysOn
AND TP3
OR SBSink
)
ST Pmp

ST:
A := X AND NOT Y;
IL:
LD X
ANDN Y
ST A

ST:
A := X OR NOT Y;
IL:
LD X
ORN Y
ST A

ST:
A := X AND NOT (Y OR Z);
IL:
LD X
ANDN (Y
OR Z
)
ST A

ST:
A := (NOT X AND Y) OR (NOT Z AND W);
IL:
LDN X
AND Y
OR (Z
NOT
AND W
)
ST A

ST:
A := (X AND Y) OR NOT (Z OR (P AND Q));
IL:
LD X
AND Y
ORN (Z
OR (P
AND Q
)
)
ST A

ST:
A := X OR Y AND Z;
IL:
LD X
OR (Y
AND Z
)
ST A

ST:
A := X OR NOT Y AND NOT Z;
IL:
LD X
OR (Y
NOT
ANDN Z
)
ST A

ST:
A := X OR NOT Y AND NOT Z OR NOT P AND Q;
IL:
LD X
OR (Y
NOT
ANDN Z
)
OR (P
NOT
AND Q
)
ST A

ST:
IF C1 THEN Q:=TRUE;
ELSIF C2 THEN Q:=FALSE;
END_IF;
IL:
LD C1
S Q
LDN C1
AND C2
R Q

ST:
IF NOT Alarm AND Stop THEN Motor:=FALSE;
END_IF;
IL:
LDN Alarm
AND Stop
R Motor

ST:
Out := A AND (B OR (C AND D));
IL:
LD A
AND (B
OR (C
AND D
)
)
ST Out

ST:
IF NOT Err AND NOT Stop AND (Timer.Q OR (Hold AND Enable)) THEN Err:=TRUE;
ELSIF Err AND ResetPB THEN Err:=FALSE;
END_IF;
IL:
LDN Err
ANDN Stop
AND (Timer.Q
OR (Hold
AND Enable
)
)
S Err

LD Err
AND ResetPB
R Err

ST:
A := X AND (Y OR NOT Z);
IL:
LD X
AND (Y
ORN Z
)
ST A

ST:
IF NOT _A AND ((X OR Y) AND NOT Z) THEN A:=1;
ELSIF _A AND ((P AND Q) OR NOT R) THEN A:=0;
END_IF;
IL:
LDN _A
AND (X
OR Y
)
ANDN Z
S A

LD _A
AND (P
AND Q
ORN R
)
R A

ST:
IF NOT _Htr AND SysOn AND NOT LTS THEN Htr:=1;
ELSIF _Htr AND (NOT SysOn OR UTS) THEN Htr:=0;
END_IF;
IL:
LDN _Htr
AND SysOn
ANDN LTS
S Htr

LD _Htr
AND (SysOn
NOT
OR UTS
)
R Htr

Source ST program:
{source_code}
"""


def build_ld_translation_prompt(source_code: str, grammar_text: str) -> str:
    return f"""Translate the following source program from ST to LD export format for CoDeSys 2.3.

Source grammar:
{grammar_text}

Translation requirements:
- The source program follows the supplied grammar.
- The source language contains assignments and IF / ELSIF / END_IF statements only.
- Expressions are boolean expressions built from identifiers, TRUE, FALSE, 1, 0, parentheses, NOT, AND, and OR.
- Generate a complete CoDeSys 2.3 LD export file.
- The output must start with this exact header:
{LD_EXPORT_HEADER}
- After the header, emit _LD_BODY and _NETWORKS : N.
- N must equal the actual number of generated _NETWORK blocks. Count only real `_NETWORK` blocks, not outputs or nested operators.
- Each direct assignment creates one _NETWORK with _NO_SET and the target variable.
- Do not skip pseudo-operator assignments such as _V := V. They are ordinary direct assignments and must generate _NO_SET networks.
- IF branch assignment to TRUE creates one _NETWORK with _OUTPUT, _POSITIV, _SET and the target variable.
- IF branch assignment to FALSE creates one _NETWORK with _OUTPUT, _NEGATIV, _SET and the target variable.
- IF with ELSIF creates two networks in source order.
- Use _LD_CONTACT for identifiers and boolean literals.
- Use _POSITIV for positive contacts and _NEGATIV for negated contacts.
- Use _LD_AND for AND expressions and _LD_OR for OR expressions.
- For every _LD_AND or _LD_OR block, _LD_OPERATOR : N must equal the number of direct contacts or nested blocks in that operator block.
- For NOT over a group, use De Morgan when needed to represent the group as LD contacts.
- Preserve dotted identifiers exactly as they appear in ST.
- Treat 1 as TRUE and 0 as FALSE.
- Never output ST keywords or ST punctuation outside the source examples in this prompt.
- Never output markdown fences, explanations, or surrounding text.
- The final line must be END_PROGRAM.
- Generate only the translated LD export.
- Before final output, count source statements and generated networks. Direct assignment = 1 network. Single IF = 1 network. IF with ELSIF = 2 networks. If the source has one IF/ELSIF and four assignments, output exactly six networks.
- Before final output, verify that every assignment target from the source appears exactly once as an output target for direct assignments and once per IF/ELSIF branch for state writes.
- Before every ENABLELIST, verify that the immediately preceding two lines are exactly:
_EXPRESSION
_POSITIV
- After every _OUTPUT line, verify that the next line is _POSITIV or _NEGATIV. Direct assignment networks must use _OUTPUT, _POSITIV, _NO_SET.
- Final LD self-check before output: `_NETWORKS : N` equals the number of `_NETWORK` blocks; every network has `_LD_ASSIGN`; every `_LD_AND` and `_LD_OR` has `_LD_OPERATOR` equal to its direct operand count; every `_LD_CONTACT` is followed by `_EXPRESSION` and a polarity; no ST syntax appears in the output.

Minimal LD assignment shape:
_NETWORK
_COMMENT
''
_END_COMMENT
_LD_ASSIGN
_LD_CONTACT
X
_EXPRESSION
_POSITIV
_EXPRESSION
_POSITIV
ENABLELIST : 0
ENABLELIST_END
_OUTPUTS : 1
_OUTPUT
_POSITIV
_NO_SET
Y

Mandatory expression closing rule:
Every network expression, including a single _LD_CONTACT, must be closed before ENABLELIST:
_EXPRESSION
_POSITIV

Mandatory direct assignment output rule:
Every direct assignment output must use this exact output block:
ENABLELIST : 0
ENABLELIST_END
_OUTPUTS : 1
_OUTPUT
_POSITIV
_NO_SET
TargetVariable

Pseudo-operator assignments use the same shape:
ST:
_Prev := Current;
LD network output:
_NO_SET
_Prev

Reference example:
ST:
Y := X AND NOT Z;
LD:
{LD_EXPORT_HEADER}
_LD_BODY
_NETWORKS : 1
_NETWORK
_COMMENT
''
_END_COMMENT
_LD_ASSIGN
_LD_AND
_LD_OPERATOR : 2
_LD_CONTACT
X
_EXPRESSION
_POSITIV
_LD_CONTACT
Z
_EXPRESSION
_NEGATIV
_EXPRESSION
_POSITIV
_EXPRESSION
_POSITIV
ENABLELIST : 0
ENABLELIST_END
_OUTPUTS : 1
_OUTPUT
_POSITIV
_NO_SET
Y
END_PROGRAM

Source ST program:
{source_code}
"""

