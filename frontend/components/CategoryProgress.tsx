interface Category {
  name: string;
  status: "researching" | "selecting" | "selected" | "all_rejected";
}

export function CategoryProgress({ categories }: { categories: Category[] }) {
  return (
    <ol className="category-progress">
      {categories.map((c) => (
        <li key={c.name} data-status={c.status}>
          {c.name}: {c.status}
        </li>
      ))}
    </ol>
  );
}
