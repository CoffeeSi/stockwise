"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { updateUserRole, userKeys, usersQueryOptions, useSessionUser, type User } from "@/entities/user";
import { Button, Card, ErrorMessage } from "@/shared/ui";
import { roleFormSchema, type RoleForm } from "../model/schema";

function UserRoleForm({ user, self }: { user: User; self: boolean }) {
  const client = useQueryClient();
  const form = useForm<RoleForm>({ resolver: zodResolver(roleFormSchema), defaultValues: { role: user.role } });
  const mutation = useMutation({ mutationFn: (input: RoleForm) => updateUserRole(user.id, input.role), onSuccess: async () => { await client.invalidateQueries({ queryKey: userKeys.all }); } });
  return <form className="space-y-2 border-t border-border py-3" onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
    <p className="text-sm font-semibold">{user.display_name} <span className="font-normal text-muted-foreground">{user.username}</span></p>
    <div className="flex gap-2"><select aria-label={`Роль ${user.display_name}`} className="rounded-xl border border-border bg-input p-2 text-sm" disabled={self || mutation.isPending} {...form.register("role")}><option value="viewer">Наблюдатель</option><option value="buyer">Закупщик</option><option value="admin">Администратор</option></select><Button type="submit" size="sm" disabled={self || mutation.isPending}>Сохранить</Button></div>
    {form.formState.errors.role && <p role="alert" className="text-xs text-destructive">{form.formState.errors.role.message}</p>}
    {mutation.isError && <ErrorMessage error={mutation.error} />}
    {mutation.isSuccess && <p role="status" className="text-xs text-muted-foreground">Роль сохранена.</p>}
  </form>;
}

export function ManageUsers() {
  const user = useSessionUser();
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const users = useQuery({ ...usersQueryOptions(offset), enabled: open && user?.role === "admin" });
  if (user?.role !== "admin") return null;
  return <><Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)}>Сотрудники</Button>{open && <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4"><Card role="dialog" aria-modal="true" aria-labelledby="users-title" className="max-h-[85vh] w-full max-w-xl overflow-auto p-6"><div className="mb-4 flex items-center justify-between"><h2 id="users-title" className="text-xl font-bold">Права сотрудников</h2><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Закрыть</Button></div>{users.isPending ? <p>Загрузка…</p> : users.isError ? <ErrorMessage error={users.error} onRetry={() => void users.refetch()} /> : <>{users.data.length === 0 && <p>Сотрудники не найдены.</p>}{users.data.map((account) => <UserRoleForm key={`${account.id}-${account.role}`} user={account} self={user.id === account.id} />)}<div className="mt-4 flex gap-2"><Button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Назад</Button><Button type="button" disabled={users.data.length < 50} onClick={() => setOffset(offset + 50)}>Далее</Button></div></>}</Card></div>}</>;
}
