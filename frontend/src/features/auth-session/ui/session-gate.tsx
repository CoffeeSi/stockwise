"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { currentUserQueryOptions, login, logout, registerUser, loginInputSchema, registrationInputSchema, SessionUserProvider, userKeys, type LoginInput, type RegistrationInput } from "@/entities/user";
import { ApiError } from "@/shared/api";
import { Button, ErrorMessage, Input } from "@/shared/ui";

function LoginForm({ registered, onRegister }: { registered: boolean; onRegister: () => void }) {
  const client = useQueryClient();
  const form = useForm<LoginInput>({ resolver: zodResolver(loginInputSchema), defaultValues: { username: "", password: "" } });
  const mutation = useMutation({ mutationFn: login, onSuccess: () => { client.clear(); window.location.assign("/"); } });
  return <form onSubmit={form.handleSubmit((values) => mutation.mutate(values))} className="space-y-4" noValidate>
    <p className="text-sm text-muted-foreground">{registered ? "Аккаунт создан с правами просмотра. Войдите; роль закупщика назначает администратор." : "Войдите в рабочую систему закупок."}</p>
    <label className="block text-sm">Логин<Input autoComplete="username" {...form.register("username")} /></label>
    {form.formState.errors.username && <p role="alert" className="text-xs text-destructive">{form.formState.errors.username.message}</p>}
    <label className="block text-sm">Пароль<Input type="password" autoComplete="current-password" {...form.register("password")} /></label>
    {form.formState.errors.password && <p role="alert" className="text-xs text-destructive">{form.formState.errors.password.message}</p>}
    {mutation.isError && <ErrorMessage title="Не удалось войти" error={mutation.error} />}
    <Button type="submit" className="w-full" disabled={mutation.isPending}>{mutation.isPending ? "Входим…" : "Войти"}</Button>
    <Button type="button" variant="ghost" onClick={onRegister}>Создать аккаунт</Button>
  </form>;
}

function RegistrationForm({ onRegistered, onLogin }: { onRegistered: () => void; onLogin: () => void }) {
  const form = useForm<RegistrationInput>({ resolver: zodResolver(registrationInputSchema), defaultValues: { username: "", display_name: "", password: "" } });
  const mutation = useMutation({ mutationFn: registerUser, onSuccess: onRegistered });
  return <form onSubmit={form.handleSubmit((values) => mutation.mutate(values))} className="space-y-4" noValidate>
    <p className="text-sm text-muted-foreground">Регистрация даёт доступ к просмотру. Права на закупки назначает администратор.</p>
    <label className="block text-sm">Имя сотрудника<Input autoComplete="name" {...form.register("display_name")} /></label>
    {form.formState.errors.display_name && <p role="alert" className="text-xs text-destructive">{form.formState.errors.display_name.message}</p>}
    <label className="block text-sm">Логин<Input autoComplete="username" {...form.register("username")} /></label>
    {form.formState.errors.username && <p role="alert" className="text-xs text-destructive">{form.formState.errors.username.message}</p>}
    <label className="block text-sm">Пароль, минимум 12 символов<Input type="password" autoComplete="new-password" {...form.register("password")} /></label>
    {form.formState.errors.password && <p role="alert" className="text-xs text-destructive">{form.formState.errors.password.message}</p>}
    {mutation.isError && <ErrorMessage title="Не удалось зарегистрироваться" error={mutation.error} />}
    <Button type="submit" className="w-full" disabled={mutation.isPending}>{mutation.isPending ? "Создаём аккаунт…" : "Зарегистрироваться"}</Button>
    <Button type="button" variant="ghost" onClick={onLogin}>Уже есть аккаунт</Button>
  </form>;
}

export function SessionGate({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const session = useQuery(currentUserQueryOptions());
  const [mode, setMode] = useState<"login" | "register" | "registered">("login");
  useEffect(() => {
    const reset = () => { void client.invalidateQueries({ queryKey: userKeys.me }); };
    window.addEventListener("stockwise:unauthorized", reset);
    return () => window.removeEventListener("stockwise:unauthorized", reset);
  }, [client]);
  if (session.isPending) return <main className="grid min-h-screen place-items-center text-muted-foreground">Проверяем сессию…</main>;
  if (session.isError && !(session.error instanceof ApiError && session.error.status === 401)) return <main className="p-8"><ErrorMessage title="Не удалось проверить сессию" error={session.error} onRetry={() => void session.refetch()} /></main>;
  if (session.isError) return <main className="grid min-h-screen place-items-center bg-background p-6"><section className="w-full max-w-md space-y-6 rounded-3xl border border-border bg-card p-7"><h1 className="text-2xl font-bold">StockWise</h1>{mode === "register" ? <RegistrationForm onRegistered={() => setMode("registered")} onLogin={() => setMode("login")} /> : <LoginForm registered={mode === "registered"} onRegister={() => setMode("register")} />}</section></main>;
  return <SessionUserProvider user={session.data}>{children}</SessionUserProvider>;
}

export function LogoutButton() {
  const client = useQueryClient();
  const mutation = useMutation({ mutationFn: logout, onSuccess: () => { client.clear(); window.location.assign("/"); } });
  return <div><Button type="button" variant="ghost" size="sm" disabled={mutation.isPending} onClick={() => mutation.mutate()}>Выйти</Button>{mutation.isError && <p role="alert" className="text-xs text-destructive">{mutation.error.message}</p>}</div>;
}
