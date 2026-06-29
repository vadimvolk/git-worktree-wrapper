---
name: sync-docs-en-to-ru
description: Sync English documentation (README.md) to Russian documentation (README.ru.md), preserving Russian language while updating structure and content. Use when the user asks to sync, update, or align README.ru.md with README.md (or asks to translate/retranslate docs from English to Russian).
---

# Sync English docs to Russian docs

Synchronize the English documentation (`README.md`) to the Russian documentation (`README.ru.md`):
- Preserve the Russian language in the output
- Update structure to match the English version if it's more complete
- Add missing sections from the English version
- Ensure both documents have the same structure and content coverage
- Maintain proper markdown formatting

## User input

The user may provide optional context in their message (for example: "sync only the Installation section", "focus on template functions", or "leave the Contributing section alone"). If they do, honor it. If they don't, perform a full sync.

## Workflow

### 1. Load both documentation files

Read both files from the project root:
- `README.md` (English — source of truth for structure and content)
- `README.ru.md` (Russian — target file to update)

### 2. Analyze structure

Compare the structure of both files:
- Extract all headings (H1, H2, H3, etc.) from both files
- Identify sections present in English but missing in Russian
- Identify sections present in Russian but missing in English
- Note any structural differences (order, nesting, etc.)

### 3. Content comparison

For each section:
- Compare content coverage (not exact text, but topics covered)
- Identify missing information in Russian version
- Note any differences in examples, code blocks, or explanations
- Check if English version has updated or new content

### 4. Sync `README.ru.md` to match `README.md`

1. **Preserve Russian language** — All prose must remain in Russian. Do NOT paste English text directly. Instead:
   - Use existing Russian text where it exists and matches the English meaning
   - For new sections, translate English content to Russian
   - For updated sections, update Russian text to match English meaning
   - Maintain the same tone and style as the existing Russian documentation

2. **Structure alignment**:
   - Add missing sections from the English version (translated to Russian)
   - Reorder sections if the English version has better organization
   - Ensure heading levels match
   - Remove sections that no longer exist in the English version

3. **Content updates**:
   - Add missing code examples, tables, or explanations (translate descriptions to Russian, keep code/examples as-is)
   - Update existing sections if English version has more complete information
   - Preserve all examples and code blocks (code stays in English, comments/descriptions translated)
   - Translate any new English text to Russian

4. **Language switcher** — Ensure the language switcher at the top is correct:
   - Russian version: `[English](README.md) | **Русский**`
   - Preserve this format

5. **Preserve formatting**:
   - Maintain emoji usage consistency
   - Preserve code block formatting
   - Keep table structures (translate table headers and content to Russian)
   - Maintain list formatting

6. **Translation guidelines**:
   - Translate all descriptive text to Russian
   - Keep code examples, commands, and technical terms in English (as they appear in Russian version)
   - Translate table headers and descriptions
   - Translate section headings
   - Maintain technical accuracy in translation

### 5. Validate

After updating, verify:
- All sections from English version are present in Russian
- Structure matches between both files
- No English descriptive text remains in Russian file (code is OK)
- Markdown formatting is correct
- Language switcher is present and correct
- All new content is properly translated

### 6. Report changes

Provide a summary of:
- Sections added (with Russian translations)
- Sections updated
- Structural changes made
- Translation notes (if any terms needed clarification)
- Any notes about content that couldn't be automatically synced

## Operating principles

- **Read-only on English file** — Never modify `README.md`
- **Russian-first** — Always write/update content in Russian
- **Structure preservation** — Match the English structure exactly
- **Content completeness** — Ensure Russian version has all information from English version
- **Formatting consistency** — Maintain consistent markdown formatting
- **Translation quality** — Provide accurate Russian translations that maintain technical accuracy

## Notes

- If the English version has content that doesn't exist in Russian, translate it to Russian
- If there are discrepancies, prefer the English version as the source of truth for structure and content
- Preserve any Russian-specific improvements that don't exist in English version (but note them in the report)
- Code blocks, commands, and technical identifiers should remain in English
- Translate all user-facing text, descriptions, and explanations to Russian