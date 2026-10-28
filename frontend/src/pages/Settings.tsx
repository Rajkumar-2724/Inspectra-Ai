import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  KeyRound,
  Lock,
  Server,
  Settings,
  Shield,
  User,
  UserPlus,
  Users,
} from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";
import { Card, FieldError, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import type { Role } from "../types";

const pwSchema = z
  .object({
    current_password: z.string().min(1, "Current password required"),
    new_password: z.string().min(8, "Must be at least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.new_password === d.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

const userSchema = z.object({
  email: z.string().email("Valid email required"),
  username: z.string().min(3, "At least 3 characters"),
  full_name: z.string().optional(),
  password: z.string().min(8, "At least 8 characters"),
  role: z.enum(["admin", "inspector", "reviewer"]),
});

export default function SettingsPage() {
  const { user, has } = useAuth();
  const qc = useQueryClient();
  const admin = has();

  const users = useQuery({ queryKey: ["users"], queryFn: Api.users, enabled: admin });
  const sys = useQuery({ queryKey: ["system"], queryFn: Api.systemStatus });

  const f1 = useForm<z.infer<typeof pwSchema>>({ resolver: zodResolver(pwSchema) });
  const f2 = useForm<z.infer<typeof userSchema>>({
    resolver: zodResolver(userSchema),
    defaultValues: { role: "inspector" },
  });
  const f3 = useForm<{ organization_name: string }>({
    values: { organization_name: sys.data?.settings?.organization_name ?? "" },
  });

  const changePw = async (v: z.infer<typeof pwSchema>) => {
    try {
      await Api.changePassword(v.current_password, v.new_password);
      toast.success("Password updated successfully");
      f1.reset();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const addUser = async (v: z.infer<typeof userSchema>) => {
    try {
      await Api.createUser(v);
      toast.success(`User '${v.username}' created`);
      f2.reset();
      qc.invalidateQueries({ queryKey: ["users"] });
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const patch = async (id: number, b: object) => {
    try {
      await Api.patchUser(id, b);
      toast.success("User updated");
      qc.invalidateQueries({ queryKey: ["users"] });
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const saveOrg = async (v: { organization_name: string }) => {
    try {
      await Api.putSettings(v);
      toast.success("Station organization settings saved");
      qc.invalidateQueries({ queryKey: ["system"] });
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <>
      <PageHeader
        title="Station Settings & User Access Control"
        subtitle="Operator credentials, hardware parameters, system diagnostics, and role-based quality control access."
      />

      <div className="grid gap-4 lg:grid-cols-2 items-start">
        {/* 1. Operator Profile Card */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <User size={14} className="text-sky-400" />
              Active Operator Profile
            </h3>
            <span className="text-[10px] font-mono text-sky-400 uppercase bg-sky-500/10 px-2 py-0.5 rounded border border-sky-400/30">
              {user?.role}
            </span>
          </div>

          <dl className="space-y-2 text-xs font-mono">
            <div className="flex justify-between border-b border-white/5 py-1">
              <dt className="text-slate-400">Full Name</dt>
              <dd className="text-white font-semibold">{user?.full_name || "—"}</dd>
            </div>
            <div className="flex justify-between border-b border-white/5 py-1">
              <dt className="text-slate-400">Username</dt>
              <dd className="text-slate-200">{user?.username}</dd>
            </div>
            <div className="flex justify-between border-b border-white/5 py-1">
              <dt className="text-slate-400">Email Address</dt>
              <dd className="text-slate-200">{user?.email}</dd>
            </div>
            <div className="flex justify-between py-1">
              <dt className="text-slate-400">Assigned Role</dt>
              <dd className="text-slate-200 uppercase">{user?.role}</dd>
            </div>
          </dl>
        </Card>

        {/* 2. Password Update Card */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <KeyRound size={14} className="text-sky-400" />
              Update Account Password
            </h3>
            <span className="text-[10px] font-mono text-slate-400">Security</span>
          </div>

          <form onSubmit={f1.handleSubmit(changePw)} className="space-y-2.5" aria-label="Change password">
            <div>
              <label className="label" htmlFor="current_password">
                Current Password
              </label>
              <input
                id="current_password"
                type="password"
                className="input"
                {...f1.register("current_password")}
              />
              <FieldError msg={f1.formState.errors.current_password?.message} />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label" htmlFor="new_password">
                  New Password
                </label>
                <input
                  id="new_password"
                  type="password"
                  className="input"
                  {...f1.register("new_password")}
                />
                <FieldError msg={f1.formState.errors.new_password?.message} />
              </div>
              <div>
                <label className="label" htmlFor="confirm">
                  Confirm Password
                </label>
                <input id="confirm" type="password" className="input" {...f1.register("confirm")} />
                <FieldError msg={f1.formState.errors.confirm?.message} />
              </div>
            </div>

            <button className="btn-primary font-mono text-xs w-full mt-1" disabled={f1.formState.isSubmitting}>
              {f1.formState.isSubmitting ? "Updating Password…" : "Update Password"}
            </button>
          </form>
        </Card>

        {/* 3. System Telemetry & Diagnostics Card */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Server size={14} className="text-sky-400" />
              Workstation Telemetry & Environment
            </h3>
            <span className="text-[10px] font-mono text-slate-400">Host Status</span>
          </div>

          {sys.isLoading ? (
            <Spinner label="Checking system diagnostics" />
          ) : (
            <dl className="space-y-2 text-xs font-mono">
              <div className="flex justify-between border-b border-white/5 py-1">
                <dt className="text-slate-400">Runtime Environment</dt>
                <dd className="text-white uppercase">{sys.data?.environment}</dd>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <dt className="text-slate-400">Max Upload Buffer</dt>
                <dd className="text-slate-200">{sys.data?.max_upload_mb} MB</dd>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <dt className="text-slate-400">Hardware Real AI Inference</dt>
                <dd className={sys.data?.real_mode_available ? "text-pass" : "text-amber-400"}>
                  {sys.data?.real_mode_available ? "Available (Trained)" : "Standby (Needs Weights)"}
                </dd>
              </div>
              <div className="flex justify-between py-1">
                <dt className="text-slate-400">System Uptime</dt>
                <dd className="text-slate-200 font-bold">
                  {Math.round((sys.data?.uptime_s ?? 0) / 60)} minutes
                </dd>
              </div>
            </dl>
          )}

          {admin && (
            <form
              onSubmit={f3.handleSubmit(saveOrg)}
              className="mt-3 border-t border-white/10 pt-3 flex items-end gap-2"
            >
              <div className="flex-1">
                <label className="label" htmlFor="org">
                  Facility / Organization Name
                </label>
                <input
                  id="org"
                  className="input font-mono !text-xs"
                  placeholder="e.g. Apex Industrial Manufacturing"
                  {...f3.register("organization_name")}
                />
              </div>
              <button className="btn-ghost font-mono text-xs">Save</button>
            </form>
          )}
        </Card>

        {/* 4. Administrator: Add User Card */}
        {admin && (
          <Card className="space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
                <UserPlus size={14} className="text-sky-400" />
                Provision Operator Account
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Admin Only</span>
            </div>

            <form onSubmit={f2.handleSubmit(addUser)} className="grid grid-cols-2 gap-2.5 font-mono text-xs" aria-label="Add user">
              <div>
                <label className="label" htmlFor="ue">
                  Email
                </label>
                <input id="ue" className="input" placeholder="inspector@plant.com" {...f2.register("email")} />
                <FieldError msg={f2.formState.errors.email?.message} />
              </div>
              <div>
                <label className="label" htmlFor="uu">
                  Username
                </label>
                <input id="uu" className="input" placeholder="op_line1" {...f2.register("username")} />
                <FieldError msg={f2.formState.errors.username?.message} />
              </div>
              <div>
                <label className="label" htmlFor="up">
                  Temporary Password
                </label>
                <input id="up" type="password" className="input" {...f2.register("password")} />
                <FieldError msg={f2.formState.errors.password?.message} />
              </div>
              <div>
                <label className="label" htmlFor="ur">
                  System Role
                </label>
                <select id="ur" className="input" {...f2.register("role")}>
                  <option value="inspector">Quality Inspector</option>
                  <option value="reviewer">Quality Reviewer</option>
                  <option value="admin">System Administrator</option>
                </select>
              </div>
              <button className="btn-primary col-span-2 !py-2 text-xs font-mono mt-1">
                Provision Account
              </button>
            </form>
          </Card>
        )}

        {/* 5. Administrator: User Management Table */}
        {admin && (
          <Card className="lg:col-span-2 space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
                <Users size={14} className="text-sky-400" />
                Station User Directory & Access Control
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Role Permissions</span>
            </div>

            {users.isLoading ? (
              <Spinner label="Loading user directory" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono">
                  <thead>
                    <tr>
                      <th className="th">Operator Handle</th>
                      <th className="th">Email Address</th>
                      <th className="th">Role Permission</th>
                      <th className="th text-right">Account Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.data?.map((u) => (
                      <tr key={u.id} className="border-t border-white/5 hover:bg-white/[0.02] text-xs">
                        <td className="td font-bold text-white">{u.username}</td>
                        <td className="td text-slate-300">{u.email}</td>
                        <td className="td">
                          <select
                            aria-label={`Role for ${u.username}`}
                            className="input !w-44 !py-0.5 text-xs font-mono"
                            value={u.role}
                            disabled={u.id === user?.id}
                            onChange={(e) => patch(u.id, { role: e.target.value as Role })}
                          >
                            <option value="inspector">Quality Inspector</option>
                            <option value="reviewer">Quality Reviewer</option>
                            <option value="admin">Administrator</option>
                          </select>
                        </td>
                        <td className="td text-right">
                          <label className="inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              aria-label={`Active ${u.username}`}
                              checked={u.is_active}
                              disabled={u.id === user?.id}
                              onChange={(e) => patch(u.id, { is_active: e.target.checked })}
                              className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-sky-500"
                            />
                            <span className="text-[11px] font-mono ml-2 text-slate-400">
                              {u.is_active ? "ENABLED" : "DISABLED"}
                            </span>
                          </label>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}
      </div>
    </>
  );
}
