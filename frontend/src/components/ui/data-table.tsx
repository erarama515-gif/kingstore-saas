"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Column<T> = {
  header: string;
  key?: keyof T;
  render?: (row: T) => ReactNode;
  className?: string;
};

export function DataTable<T extends { id?: string }>({
  rows,
  columns,
  emptyMessage = "لا توجد بيانات",
  onRowClick,
}: {
  rows: T[];
  columns: Column<T>[];
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
}) {
  return (
    <div className="border rounded-lg overflow-hidden bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            {columns.map((c, i) => (
              <th
                key={i}
                className={cn("text-right px-4 py-3 font-semibold", c.className)}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="text-center px-4 py-10 text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr
                key={(row.id as string) || ri}
                className={cn(
                  "border-t hover:bg-muted/30 transition-colors",
                  onRowClick && "cursor-pointer",
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((c, ci) => (
                  <td key={ci} className={cn("px-4 py-3", c.className)}>
                    {c.render ? c.render(row) : String(row[c.key as keyof T] ?? "")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
