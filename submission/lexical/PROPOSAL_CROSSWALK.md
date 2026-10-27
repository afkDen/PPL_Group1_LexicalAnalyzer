# Proposal vocabulary reconciliation

The preserved group proposal has 11 original pages plus eight revision-2 pages.
Revision-2 page14 lists all 28 current lexical keywords and 21 original reserved
names. None is omitted: lexical_inventory.json contains them all, plus the
accepted numerical correction's Float, int_float, float_int, float_text.

Original pages4/7 (no power/block comments/noise) are superseded by the revision-2
amendment. Revision-2 page13's truncating Int slash is superseded by the professor's
real-division clarification: `/` real, `div` integer floor; seven arithmetic and
nine Boolean/relational operations are required counts, not points. Float is the
fifth lexical literal family; Unit is a two-token expression, not a replacement
for one of the four required lexical literal kinds.

Page15's completed-word lookup wording is superseded by the current strict
character-state requirement. The implemented name trie advances during scanning;
terminal states classify keywords/reserved names at boundaries. The classroom
report is now exactly TOKEN TYPE and LEXEME; the richer compiler diagnostic TSV
is an internal API and is not substituted for this submission's report.

The analyzer recognizes lexemes only. Namespace redeclaration, Int64/finite Float
range checks, parsing and execution are later compiler phases. The lexical
example's inventory tail is deliberate and is not claimed to be an executable
program. Group members should print the latest proposal with these corrections
and prepare their physical index card.
