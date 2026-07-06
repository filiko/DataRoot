import { API } from "../config/api";
import type { PenFile } from "../types/pen";

export type SqlDialect = "auto" | "postgres" | "mysql" | "sqlite";

export const SQL_DIALECT_OPTIONS: { value: SqlDialect; label: string }[] = [
  { value: "auto", label: "Auto-detect" },
  { value: "postgres", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL / MariaDB" },
  { value: "sqlite", label: "SQLite" },
];

export interface SqlImportWarning {
  code: string;
  message: string;
  statement?: string | null;
}

export interface SqlImportResponse {
  project_id: string;
  pen: PenFile;
  warnings: SqlImportWarning[];
  stats: Record<string, number>;
}

export async function importSqlText(
  sql: string,
  dialect: SqlDialect = "auto",
  projectName = "Imported Schema",
  sourceName = "pasted DDL",
): Promise<SqlImportResponse> {
  const response = await fetch(API.importSql(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sql,
      dialect,
      project_name: projectName,
      source_name: sourceName,
    }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function importSqlFile(
  file: File,
  dialect: SqlDialect = "auto",
): Promise<SqlImportResponse> {
  const sql = await file.text();
  const projectName = file.name.replace(/\.[^.]+$/, "");
  return importSqlText(sql, dialect, projectName, file.name);
}
