"""Check which rows players fail on in May 9 puzzle."""
import csv
from collections import Counter

wrong_by_row = Counter()
correct_by_row = Counter()
wrong_words = Counter()

with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        if not row['created_at'].startswith('2026-05-09'):
            continue
        if row['name'] != 'relink_guess_submitted':
            continue
        props = row.get('properties', '')
        if 'mouaw3d1-g9ugg95' not in props:
            continue
        if "'attempts_remaining':'999'" in props:
            continue
        if "'phase':'imposters'" not in props:
            continue

        # Extract row_index
        row_idx = ''
        idx = props.find("'row_index':'")
        if idx >= 0:
            start = idx + len("'row_index':'")
            end = props.find("'", start)
            row_idx = props[start:end]

        # Extract is_correct
        is_correct = "'is_correct':'true'" in props

        # Extract selected_word
        word = ''
        idx = props.find("'selected_word':'")
        if idx >= 0:
            start = idx + len("'selected_word':'")
            end = props.find("'", start)
            word = props[start:end]

        if is_correct:
            correct_by_row[row_idx] += 1
        else:
            wrong_by_row[row_idx] += 1
            wrong_words[(row_idx, word)] += 1

print('Row  Correct  Wrong  Correct%')
for r in sorted(set(list(wrong_by_row.keys()) + list(correct_by_row.keys()))):
    c = correct_by_row[r]
    w = wrong_by_row[r]
    print(f"  {r}    {c:>6}  {w:>5}   {100*c/(c+w):.0f}%")

print()
print('Most common wrong guesses (top 20):')
for (r, word), count in wrong_words.most_common(20):
    print(f"  Row {r}: \"{word}\" guessed wrong {count} times")
