"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileSpreadsheet, RotateCcw, Upload, X } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useForm } from "react-hook-form";
import { importBatchQueryOptions, uploadImportFile, type ImportBatch } from "@/entities/import-batch";
import { ApiError } from "@/shared/api";
import { useSessionUser } from "@/entities/user";
import { Button, Card } from "@/shared/ui";
import { importFormSchema, type ImportFormInput } from "../model/schema";

const sourceOptions = [
  { value: "sales", label: "История продаж" },
  { value: "monthly_sales", label: "Продажи по месяцам" },
  { value: "inventory", label: "Остатки" },
  { value: "stockout", label: "Периоды дефицита" },
  { value: "in_transit", label: "Товары в пути" },
  { value: "seasonality", label: "Сезонность" },
  { value: "supplier_terms", label: "MOQ и условия поставщиков" },
  { value: "growth", label: "Допущения о росте" },
  { value: "material_requirements", label: "Материальная потребность" },
] as const;

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "duplicate_import") return "Этот файл уже был импортирован.";
    if (error.code === "invalid_import_file") return "Сервер отклонил файл. Проверьте формат .xlsx и размер до 25 МБ.";
    if (error.code === "invalid_import_data") return "Сервер обнаружил ошибки в данных Excel. Подробности указаны ниже.";
  }
  return error instanceof Error ? error.message : "Не удалось загрузить файл. Повторите попытку.";
}

function getValidationMessage(value: unknown): string {
  if (typeof value !== "object" || value === null) return "Некорректные данные в файле.";
  if ("missing_columns" in value && Array.isArray(value.missing_columns)) {
    return `Отсутствуют столбцы: ${value.missing_columns.filter((column): column is string => typeof column === "string").join(", ")}.`;
  }
  const row = "row" in value && typeof value.row === "number" ? `Строка ${value.row}: ` : "";
  const rawMessage = "message" in value && typeof value.message === "string" ? value.message : "";
  const message = rawMessage === "invalid row values"
    ? "Некорректные значения в строке."
    : rawMessage === "invalid workbook columns"
      ? "Некорректные столбцы в книге Excel."
      : rawMessage || "Некорректные данные в файле.";
  return `${row}${message}`;
}

function detectSourceType(fileName: string): ImportFormInput["sourceType"] | null {
  const name = fileName.toLocaleLowerCase("ru").replace(/ё/g, "е");
  if (name.includes("moq")) return "supplier_terms";
  if (name.includes("динамика продаж")) return "sales";
  if (name.includes("ежемесячные продажи")) return "monthly_sales";
  if (name.includes("ежемесячные остатки")) return "inventory";
  if (name.includes("путь иэк")) return "in_transit";
  if (name.includes("сезонность")) return "seasonality";
  return null;
}

export function ImportDataAction({ onImported, onStartCalculation }: { onImported?: (batch: ImportBatch) => void; onStartCalculation?: () => void }) {
  const user = useSessionUser();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const notifiedBatchIdRef = useRef<string | null>(null);
  const { register, handleSubmit, setValue, watch, formState: { errors }, reset } = useForm<ImportFormInput>({
    resolver: zodResolver(importFormSchema),
    defaultValues: { sourceType: "sales" },
    mode: "onChange",
  });
  const file = watch("file");

  const mutation = useMutation({
    mutationFn: (values: ImportFormInput) => uploadImportFile({
      file: values.file,
      sourceType: values.sourceType,
      onProgress: (loaded, total) => setProgress(total > 0 ? Math.min(100, Math.round(loaded / total * 100)) : null),
    }),
    onMutate: () => {
      setProgress(0);
      setBatchId(null);
    },
    onSuccess: (batch) => {
      setProgress(100);
      setBatchId(batch.batch_id);
    },
  });

  const statusQuery = useQuery({
    ...importBatchQueryOptions(batchId ?? ""),
    enabled: batchId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 2000 : false;
    },
  });
  const batch = statusQuery.data ?? (mutation.isSuccess ? mutation.data : null);

  useEffect(() => {
    if (batch?.status === "completed" && notifiedBatchIdRef.current !== batch.batch_id) {
      notifiedBatchIdRef.current = batch.batch_id;
      onImported?.(batch);
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
    }
  }, [batch, onImported, queryClient]);

  function chooseFile(nextFile: File | undefined) {
    if (!nextFile) return;
    setValue("file", nextFile, { shouldDirty: true, shouldValidate: true });
    const sourceType = detectSourceType(nextFile.name);
    if (sourceType) setValue("sourceType", sourceType, { shouldDirty: true, shouldValidate: true });
    setBatchId(null);
    setProgress(null);
    mutation.reset();
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  function closeDialog() {
    if (mutation.isPending) return;
    setOpen(false);
  }

  function clearForm() {
    if (mutation.isPending) return;
    reset({ sourceType: "sales" });
    if (fileInputRef.current) fileInputRef.current.value = "";
    setBatchId(null);
    setProgress(null);
    mutation.reset();
  }

  const uploadInProgress = mutation.isPending;
  const serverProcessing = batch?.status === "pending" || batch?.status === "processing";
  const complete = batch?.status === "completed";
  const failed = batch?.status === "failed";
  const validationErrors = mutation.isError && mutation.error instanceof ApiError && mutation.error.validationErrors.length > 0
    ? mutation.error.validationErrors
    : batch?.validation_errors ?? [];
  const showUploadProgress = uploadInProgress && progress !== null;
  const serverStage = batch?.progress?.stage;
  const stageLabel = serverStage === "uploaded" ? "Файл в очереди" : serverStage === "validating" ? "Проверка Excel" : serverStage === "persisting" ? "Сохранение строк" : "Обработка импорта";
  const processed = batch?.progress?.processed_rows ?? 0;
  const totalRows = batch?.progress?.total_rows;
  if (user?.role !== "buyer" && user?.role !== "admin") return null;

  return <>
    <Button type="button" variant="secondary" onClick={() => setOpen(true)}><Upload className="h-4 w-4" />Загрузить файлы (1С/Excel)</Button>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
      <Card role="dialog" aria-modal="true" aria-labelledby="import-title" className="max-h-[90vh] w-full max-w-xl overflow-y-auto p-5 shadow-2xl sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-wider text-accent-foreground">Импорт данных</p><h2 id="import-title" className="mt-1 text-xl font-bold">Загрузить Excel-файл</h2><p className="mt-2 text-sm text-muted-foreground">Укажите тип источника, затем выберите файл .xlsx до 25 МБ.</p></div>
          <button type="button" aria-label="Закрыть окно импорта" onClick={closeDialog} disabled={uploadInProgress} className="rounded-xl p-2 text-muted-foreground hover:bg-card-muted hover:text-foreground disabled:opacity-50"><X className="h-5 w-5" /></button>
        </div>
        <form className="mt-6 space-y-5" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <label className="block text-sm font-medium" htmlFor="import-source">Тип источника</label>
          <select id="import-source" {...register("sourceType")} disabled={uploadInProgress || serverProcessing} className="-mt-3 h-11 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground outline-none focus:border-ring">
            {sourceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          {errors.sourceType && <p role="alert" className="text-xs text-destructive">{errors.sourceType.message}</p>}
          <input ref={fileInputRef} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={onFileChange} className="sr-only" aria-label="Выбрать Excel-файл" />
          <button type="button" onClick={() => fileInputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} disabled={uploadInProgress || serverProcessing} className={`flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-5 py-8 text-center transition disabled:cursor-not-allowed disabled:opacity-50 ${dragging ? "border-primary bg-accent" : "border-border bg-card-muted hover:border-primary/60"}`}>
            <FileSpreadsheet className="h-8 w-8 text-accent-foreground" /><span className="text-sm font-semibold">{file ? file.name : "Перетащите Excel-файл сюда"}</span><span className="text-xs text-muted-foreground">{file ? `${(file.size / 1024 / 1024).toFixed(2)} МБ · нажмите, чтобы заменить` : "или нажмите для выбора"}</span>
          </button>
          {errors.file && <p role="alert" className="text-xs text-destructive">{errors.file.message}</p>}
          {(uploadInProgress || serverProcessing) && <div role="status" aria-live="polite" className="rounded-xl border border-border bg-card-muted p-4">
            <div className="flex justify-between gap-3 text-xs"><span className="font-semibold">{uploadInProgress ? progress === 100 ? "Файл передан, сервер проверяет данные…" : "Загрузка файла…" : "Обработка импорта на сервере…"}</span>{showUploadProgress && <span>{progress}%</span>}</div>
            {showUploadProgress && <progress className="mt-3 h-2 w-full accent-primary" value={progress ?? 0} max={100} aria-label="Передача файла" />}
            {serverProcessing && <p className="mt-2 text-xs text-muted-foreground">{stageLabel}: {processed}{totalRows == null ? " строк" : ` из ${totalRows} строк`}</p>}
          </div>}
          {mutation.isError && <div role="alert" className="flex gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"><AlertCircle className="h-4 w-4 shrink-0" /><span>{getErrorMessage(mutation.error)}</span></div>}
          {statusQuery.isError && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"><p>Не удалось получить статус импорта: {getErrorMessage(statusQuery.error)}</p><Button type="button" variant="secondary" size="sm" className="mt-2" onClick={() => void statusQuery.refetch()}><RotateCcw className="h-3.5 w-3.5" />Повторить</Button></div>}
          {complete && batch && <div role="status" className="flex gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-500"><CheckCircle2 className="h-4 w-4 shrink-0" /><span>Импорт завершён: обработано {batch.row_count} строк. ID партии: {batch.batch_id}</span></div>}
          {complete && <div className="rounded-xl border border-border bg-card-muted p-3 text-sm"><p>После загрузки нужных источников запустите новый расчёт. Импорт сам по себе не создаёт рекомендации.</p>{onStartCalculation && <Button type="button" size="sm" className="mt-3" onClick={() => { setOpen(false); onStartCalculation(); }}>Запустить расчёт</Button>}</div>}
          {complete && batch?.warnings.map((warning, index) => <div key={index} role="status" className="rounded-xl border border-border bg-card-muted p-3 text-xs text-muted-foreground">{warning.code === "missing_moq" ? `Пропущено ${warning.count} строк без значения MOQ. Проверьте исходный файл, если нужны условия поставки для этих товаров.` : `Импорт завершён с предупреждением: ${warning.code}.`}</div>)}
          {failed && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">Обработка файла завершилась ошибкой. Проверьте структуру Excel и повторите загрузку.</div>}
          {validationErrors.length > 0 && <div className="rounded-xl border border-border bg-card-muted p-3 text-xs"><p className="font-semibold">Ошибки валидации</p><ul className="mt-2 list-disc space-y-1 pl-5">{validationErrors.slice(0, 8).map((issue, index) => <li key={index}>{getValidationMessage(issue)}</li>)}</ul>{validationErrors.length > 8 && <p className="mt-2 text-muted-foreground">И ещё {validationErrors.length - 8} ошибок.</p>}</div>}
          <div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="ghost" onClick={clearForm} disabled={uploadInProgress}>Очистить</Button><Button type="submit" disabled={uploadInProgress || serverProcessing || complete}>{uploadInProgress ? "Загрузка…" : failed || mutation.isError ? "Повторить загрузку" : "Загрузить файл"}</Button></div>
        </form>
      </Card>
    </div>}
  </>;
}
