"use client";

import { ReactNode } from "react";
import Link from "next/link";
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
  rowHref,
  rowKey,
}: {
  rows: T[];
  columns: Column<T>[];
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  /** If provided, wrap the row in a link to this href (overrides onRowClick). */
  rowHref?: (row: T) => string;
  /** Optional stable key extractor (falls back to row.id or index). */
  rowKey?: (row: T) => string;
}) {
  const interactive = !!onRowClick || !!rowHref;
  return (
    <div className="border rounded-xl overflow-hidden bg-card shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {columns.map((c, i) => (
                <th
                  key={i}
                  className={cn(
                    "text-right px-4 py-3 font-semibold text-xs uppercase tracking-wider text-muted-foreground",
                    c.className,
                  )}
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
                  className="text-center px-4 py-12 text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, ri) => {
                const key = rowKey?.(row) ?? (row.id as string) ?? String(ri);
                const cells = columns.map((c, ci) => (
                  <td key={ci} className={cn("px-4 py-3 align-middle", c.className)}>
                    {c.render ? c.render(row) : String(row[c.key as keyof T] ?? "")}
                  </td>
                ));
                if (rowHref) {
                  // Link-as-row: each cell is wrapped via a relative anchor;
                  // we still set tr as the click target via JS for whole-row hit.
                  return (
                    <tr
                      key={key}
                      className="border-t hover:bg-muted/40 cursor-pointer transition-colors"
                    >
                      {columns.map((c, ci) => (
                        <td key={ci} className={cn("px-0", c.className)}>
                          <Link
                            href={rowHref(row)}
                            className="block px-4 py-3 w-full h-full"
                          >
                            {c.render ? c.render(row) : String(row[c.key as keyof T] ?? "")}
                          </Link>
                        </td>
                      ))}
                    </tr>
                  );
                }
                return (
                  <tr
                    key={key}
                    className={cn(
                      "border-t hover:bg-muted/40 transition-colors",
                      interactive && "cursor-pointer",
                    )}
                    onClick={() => onRowClick?.(row)}
                  >
                    {cells}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
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
    <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {action && <div className="flex gap-2">{action}</div>}
    </div>
  );
}

/** Generic skeleton loader for tables and dashboards. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="border rounded-xl overflow-hidden bg-card shadow-sm">
      <div className="bg-muted/40 px-4 py-3 border-b">
        <div className="h-3 w-32 bg-muted-foreground/20 rounded animate-pulse" />
      </div>
      <div className="divide-y">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-4">
            <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            <div className="h-4 w-32 bg-muted animate-pulse rounded" />
            <div className="h-4 flex-1 bg-muted animate-pulse rounded" />
            <div className="h-4 w-20 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
