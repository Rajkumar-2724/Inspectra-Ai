import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, ScanSearch, ShieldCheck, User } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";
import { FieldError } from "../components/ui";
import VideoBackdrop from "../components/VideoBackdrop";
import { useAuth } from "../contexts/AuthContext";
import { errMsg } from "../services/api";

const schema = z.object({
  username: z.string().min(1, "Enter your username or email"),
  password: z.string().min(1, "Enter your password"),
});
type F = z.infer<typeof schema>;

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<F>({ resolver: zodResolver(schema) });

  if (user) return <Navigate to="/" replace />;

  const submit = async (v: F) => {
    try {
      await login(v.username, v.password);
      toast.success("Workstation session authenticated");
      nav("/");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const fillQuick = (u: string, p: string) => {
    setValue("username", u);
    setValue("password", p);
  };

  return (
    <div className="bg-field relative grid min-h-full place-items-center p-4 overflow-hidden">
      <VideoBackdrop src="/background.mp4" poster="/background.png" />
      <div className="relative z-10 w-full max-w-md space-y-4">
        {/* Workstation Header */}
        <div className="text-center space-y-1">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-lg bg-sky-500/10 border border-sky-400/30 text-sky-400 mb-2">
            <ScanSearch size={24} />
          </div>
          <h1 className="text-xl font-bold tracking-wider text-white uppercase font-mono">
            AVI Quality Workstation
          </h1>
          <p className="text-xs text-slate-400 font-mono">
            AI-Based Automated Visual Inspection Platform
          </p>
        </div>

        {/* Form Card */}
        <form
          onSubmit={handleSubmit(submit)}
          className="glass p-6 sm:p-7 space-y-4 border border-white/10"
          aria-label="Sign in"
        >
          <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Lock size={13} className="text-sky-400" />
              Operator Authentication
            </span>
            <span className="text-[10px] font-mono text-slate-400 uppercase bg-slate-800 px-2 py-0.5 rounded">
              SECURE ACCESS
            </span>
          </div>

          <div>
            <label className="label" htmlFor="username">
              Username or email
            </label>
            <input
              id="username"
              className="input font-mono !text-xs"
              autoComplete="username"
              placeholder="operator_handle or email"
              {...register("username")}
            />
            <FieldError msg={errors.username?.message} />
          </div>

          <div>
            <label className="label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="input font-mono !text-xs"
              autoComplete="current-password"
              placeholder="••••••••"
              {...register("password")}
            />
            <FieldError msg={errors.password?.message} />
          </div>

          <button
            className="btn-primary w-full !py-2.5 font-mono text-xs font-semibold tracking-wide"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Authenticating Session…" : "Sign In to Workstation"}
          </button>

          {/* Station Credentials for Operator Access */}
          <div className="rounded border border-white/5 bg-ink-950/70 p-2.5 text-[11px] font-mono text-slate-400 space-y-1">
            <div className="text-[10px] uppercase text-slate-400 font-bold flex items-center gap-1">
              <ShieldCheck size={12} className="text-sky-400" />
              Default Station Accounts (Click to autofill):
            </div>
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              <button
                type="button"
                className="btn-ghost !px-2 !py-0.5 !text-[10px]"
                onClick={() => fillQuick("admin", "ChangeMe-Admin-123")}
              >
                Admin (admin)
              </button>
              <button
                type="button"
                className="btn-ghost !px-2 !py-0.5 !text-[10px]"
                onClick={() => fillQuick("inspector", "ChangeMe-Admin-123")}
              >
                Inspector (inspector)
              </button>
              <button
                type="button"
                className="btn-ghost !px-2 !py-0.5 !text-[10px]"
                onClick={() => fillQuick("reviewer", "ChangeMe-Admin-123")}
              >
                Reviewer (reviewer)
              </button>
            </div>
          </div>

          <p className="text-center text-xs font-mono text-slate-400 pt-1">
            New operator?{" "}
            <Link to="/register" className="text-sky-400 hover:underline">
              Create account
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
