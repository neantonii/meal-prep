# Recipe Sites

The sites the meal-recipe skill researches and cites (SKILL.md §1). The
cloud environment's network allowlist should mirror this list: every host
marked **allowed** belongs on it, so `curl` reaches it with no setup.
Research starts here; the web-search tool finds pages (it runs outside the sandbox), curl
reads them.

Status was checked by fetching one recipe page per host through the
session proxy.

| Host | Language / focus | Recipe data | Status |
|---|---|---|---|
| `natashaskitchen.com` | EN, Russian/Ukrainian home cooking | JSON-LD | allowed |
| `valentinascorner.com` | EN, Slavic family cooking | JSON-LD | allowed |
| `www.recipesfromeurope.com` | EN, European classics (shchi, borscht) | JSON-LD | allowed |
| `www.olgasflavorfactory.com` | EN, Russian/Ukrainian home cooking | JSON-LD | allowed |
| `www.budgetbytes.com` | EN, budget and meal-prep cooking | JSON-LD | allowed |
| `www.recipetineats.com` | EN, well-tested everyday recipes | JSON-LD | allowed |
| `ciaoflorentina.com` | EN, Mediterranean | JSON-LD | allowed |
| `www.russianfood.com` | RU, large Russian recipe collection | page text only (cp1251) | allowed |
| `eda.ru` | RU | — | dropped: the site resets the connection |
| `mydeliciousmeals.com` | EN | — | dropped: no recipe data on the page |
| `www.seriouseats.com` | EN, technique-heavy | — | refused by the environment service |

## Before researching

A session can run in an environment that lacks some of these hosts (a new
environment, the Default one, or an allowlist edited by hand). Before the
first lookup, read the environment's allowed hosts (the environment tool,
e.g. `get_environment`) and compare them with every host marked
**allowed** above. If any are missing, propose adding all of the missing
ones in one request (the user approves), then start. Do not research
around the gap, and do not skip it because one site happens to be
reachable. If the user declines, say which sites stay unreachable and
research from the rest.

## Reading a page

- **JSON-LD sites:** extract the `<script type="application/ld+json">`
  block whose `@type` is `Recipe` (ingredients, steps, yield, times).
- **Page-text sites** (`www.russianfood.com`): decode as cp1251
  (`iconv -f cp1251 -t utf-8`), then read the ingredient list and steps
  from the page text.

## Adding a site

When a needed recipe lives on a site not listed here, propose the exact
host for the environment's allowed hosts (the user approves), fetch one
recipe page to fill in the "Recipe data" column, and add a row here in
the same change. A host the environment refuses gets a row too, so it is
not retried.
