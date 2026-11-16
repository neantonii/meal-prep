import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import type { Bin, CatalogEntry, CatalogGroup, UnassignedRecipe } from "../api";
import type { DragData } from "../dnd";
import Shelf from "./Shelf";

interface Props {
  groups: CatalogGroup[];
  /** Portions with no day yet, and the bin: listed above the recipes. */
  unassigned: UnassignedRecipe[];
  bin: Bin;
  today: string;
}

export default function Palette({ groups, unassigned, bin, today }: Props) {
  const [query, setQuery] = useState("");

  return (
    <aside className="palette">
      <Shelf unassigned={unassigned} bin={bin} today={today} />
      <input
        type="search"
        placeholder="Search recipes…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {groups.map((g) => (
        <details className="cat" key={g.category} open>
          <summary title={g.description}>{g.label}</summary>
          {g.recipes
            .filter((r) => r.title.toLowerCase().includes(query.toLowerCase()))
            .map((r) => (
              <RecipeChip key={r.id} recipe={r} category={g.category} />
            ))}
        </details>
      ))}
    </aside>
  );
}

/** A recipe to drag onto a day: cooks one more batch of it. */
function RecipeChip({ recipe, category }: { recipe: CatalogEntry; category: string }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `recipe:${recipe.id}`,
    data: { kind: "recipe", recipe: recipe.id, title: recipe.title } satisfies DragData,
  });
  return (
    <div ref={setNodeRef} className={`chip${isDragging ? " dragging" : ""}`} {...attributes} {...listeners}>
      <a href={`/cards/recipe/${category}/${recipe.id}.html`} target="_blank" rel="noreferrer">
        {recipe.title}
      </a>{" "}
      <span className="kcal">
        {Math.round(recipe.kcal)} kcal · {Math.round(recipe.protein_g)}P
      </span>
    </div>
  );
}
