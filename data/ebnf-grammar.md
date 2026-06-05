```ebnf
<program> ::= { <statement> }

<statement> ::= <assignment> | <if-statement>

<if-statement> ::= "IF" <expression> "THEN" <assignment>
                   [ "ELSIF" <expression> "THEN" <assignment> ]
                   "END_IF" ";"

<assignment> ::= <identifier> ":=" <expression> ";"

<expression> ::= <or_expression>

<or_expression> ::= <and_expression> { "OR" <and_expression> }

<and_expression> ::= <not_expression> { "AND" <not_expression> }

<not_expression> ::= "NOT" <not_expression> | <primary>

<bool_literal> ::= "TRUE" | "FALSE" | "1" | "0"

<primary> ::= <identifier> | <bool_literal> | "(" <expression> ")"

<identifier> ::= <name> { "." <name> }

<name> ::= ( <letter> | "_" ) { <letter> | <digit> | "_" }

<letter> ::= "A" | ... | "Z" | "a" | ... | "z"

<digit> ::= "0" | ... | "9"
