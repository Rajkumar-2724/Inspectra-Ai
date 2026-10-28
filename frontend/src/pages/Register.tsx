import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, ScanSearch, UserPlus } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { FieldError } from "../components/ui";
import VideoBackdrop from "../components/VideoBackdrop";
import { Api, errMsg } from "../services/api";

const schema = z
  .object({
    full_name: z.string().max(128).optional(),
    email: z.string().email("Enter a valid email address"),
    username: z
      .string()
      .min(3, "At least 3 characters")
      .regex(/^[A-Za-z0-9_.-]+$/, "Letters, numbers, . _ - only"),
    password: z.string().min(8, "At least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });
type F = z.infer<typeof schema>;

export default function Register() {
  const nav = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<F>({ resolver: zodResolver(schema) });

  const submit = async (v: F) => {
    try {
      await Api.register({
        email: v.email,
        username: v.username,
        full_name: v.full_name ?? "",
        password: v.password,
      });
      toast.success("Account provisioned. Please sign in.");
      nav("/login");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const fields: [keyof F, string, string, string][] = [
    ["full_name", "Full Name", "text", "e.g. John Doe"],
    ["email", "Workstation Email", "email", "operator@plant.com"],
    ["username", "Operator Username", "text", "op_alex"],
    ["password", "Password", "password", "••••••••"],
    ["confirm", "Confirm Password", "password", "••••••••"],
  ];

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
            Provision Operator Account
          </h1>
          <p className="text-xs text-slate-400 font-mono">
            Quality Inspection Workstation Registration
          </p>
        </div>

        {/* Register Form */}
        <form
          onSubmit={handleSubmit(submit)}
          className="glass p-6 sm:p-7 space-y-3.5 border border-white/10"
          aria-label="Create account"
        >
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <UserPlus size={13} className="text-sky-400" />
              Operator Credentials
            </span>
            <span className="text-[10px] font-mono text-slate-400">ROLE: INSPECTOR</span>
          </div>

          <p className="text-[11px] font-mono text-slate-400">
            Self-registered accounts are granted Quality Inspector permissions. An administrator can elevate permissions to Reviewer or Admin.
          </p>

          {fields.map(([k, l, t, placeholder]) => (
            <div key={k}>
              <label className="label" htmlFor={k}>
                {l}
              </label>
              <input
                id={k}
                type={t}
                placeholder={placeholder}
                className="input font-mono !text-xs"
                {...register(k)}
              />
              <FieldError msg={errors[k]?.message} />
            </div>
          ))}

          <button
            className="btn-primary w-full !py-2.5 font-mono text-xs font-semibold tracking-wide mt-2"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Provisioning Account…" : "Create Operator Account"}
          </button>

          <p className="text-center text-xs font-mono text-slate-400 pt-1">
            Already provisioned?{" "}
            <Link to="/login" className="text-sky-400 hover:underline">
              Sign In to Workstation
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
