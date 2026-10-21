import { useState } from "react";
import type { CatalogGroup } from "../api";

interface Props {
  groups: CatalogGroup[];
}

export default function Palette({ groups }: Props) {
  const [query, setQuery] = useState("");

  return (
    <aside className="palette">
      <input
        type="search"
        placeholder="Search recipes…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {groups.map((g) => (
        <details className="cat" key={g.category} open>
          <summary>{g.category}</summary>
          {g.recipes
            .filter((r) => r.title.toLowerCase().includes(query.toLowerCase()))
            .map((r) => (
              <div
                className="chip"
                key={r.id}
                draggable
                onDragStart={(e) => e.dataTransfer.setData("text/recipe-id", r.id)}
              >
                <a
                  href={`/cards/recipe/${g.category}/${r.id}.html`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  {r.title}
                </a>{" "}
                <span className="kcal">
                  {Math.round(r.kcal)} kcal · {Math.round(r.protein_g)}P
                </span>
              </div>
            ))}
        </details>
      ))}
    </aside>
  );
}
