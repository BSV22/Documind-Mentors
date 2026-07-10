"use client";

import { useState, useEffect, useContext } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { AuthContext } from "../context/AuthContext";
import { apiPost } from "../utils/api";

export default function AuthPage({ onAuthSuccess }) {
  const auth = useContext(AuthContext);
  const [mode, setMode] = useState("signIn");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [otp, setOtp] = useState("");
  const [verificationEmail, setVerificationEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    console.log("AuthPage mounted. Current mode:", mode);
    const timer = setTimeout(() => {
      setMounted(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");
    console.log("handleSubmit triggered. Mode:", mode, "Email:", email);
    
    try {
      const endpoint = mode === "signIn" ? "/api/auth/signin" : "/api/auth/signup";
      const payload = {
        email,
        password,
        ...(mode === "signUp" && { name }),
      };

      console.log("Calling API endpoint:", endpoint, "with payload:", payload);
      const data = await apiPost(endpoint, payload);
      console.log("API response received:", data);

      if (data.status === "verification_required") {
        console.log("Setting mode to verifyOtp. Target email:", data.email);
        setVerificationEmail(data.email);
        setMode("verifyOtp");
        setOtp("");
      } else {
        console.log("Verification not required. User data:", data.user);
        auth.login(null, data.user);
        onAuthSuccess?.(data.user);
      }
    } catch (err) {
      console.error("Authentication error caught:", err);
      if (err.message.includes("verification pending") || err.message.includes("pending")) {
        console.log("Verification pending. Redirecting to verifyOtp for:", email);
        setVerificationEmail(email);
        setMode("verifyOtp");
        setOtp("");
      } else {
        setLocalError(err.message || "Authentication failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOtpSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLocalError("");
    console.log("handleOtpSubmit triggered. Email:", verificationEmail, "OTP:", otp);

    try {
      const data = await apiPost("/api/auth/verify-otp", {
        email: verificationEmail,
        otp
      });
      console.log("OTP Verification response:", data);

      auth.login(null, data.user);
      onAuthSuccess?.(data.user);
    } catch (err) {
      console.error("OTP verification error:", err);
      setLocalError(err.message || "OTP verification failed");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setLoading(true);
    setLocalError("");
    console.log("handleResendOtp triggered for:", verificationEmail);

    try {
      const data = await apiPost("/api/auth/resend-otp", {
        email: verificationEmail
      });
      console.log("Resend OTP response:", data);
      alert(data.message || "Verification code resent successfully!");
    } catch (err) {
      console.error("Resend OTP error:", err);
      setLocalError(err.message || "Failed to resend verification code");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setLoading(true);
    setLocalError("");
    console.log("Google Auth Success. Verifying with backend...");
    try {
      const jwtToken = credentialResponse.credential;
      const data = await apiPost("/api/auth/google", { token: jwtToken });
      console.log("Google Auth backend response:", data);

      auth.login(null, data.user);
      onAuthSuccess?.(data.user);
    } catch (err) {
      console.error("Google login backend error:", err);
      setLocalError(err.message || "Google login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    setLocalError("Google login failed. Please try again.");
    console.error("Google login failed");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md rounded-4xl border border-slate-800 bg-slate-900/95 p-8 shadow-2xl shadow-slate-950/40">
        
        {mode !== "verifyOtp" ? (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Welcome to Documind
                </p>
                <h1 className="mt-3 text-3xl font-semibold">{mode === "signIn" ? "Sign In" : "Create Account"}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  {mode === "signIn"
                    ? "Access your dashboard and continue your work."
                    : "Create a new account to save your workspace settings."}
                </p>
              </div>

              <div className="flex items-center rounded-3xl bg-slate-950/80 p-1 text-sm uppercase tracking-[0.22em] text-slate-400">
                <button
                  type="button"
                  onClick={() => {
                    console.log("Switching mode to signIn");
                    setMode("signIn");
                  }}
                  className={`flex-1 rounded-3xl px-4 py-3 transition cursor-pointer ${
                    mode === "signIn"
                      ? "bg-cyan-500 text-slate-950"
                      : "hover:bg-slate-800"
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    console.log("Switching mode to signUp");
                    setMode("signUp");
                  }}
                  className={`flex-1 rounded-3xl px-4 py-3 transition cursor-pointer ${
                    mode === "signUp"
                      ? "bg-cyan-500 text-slate-950"
                      : "hover:bg-slate-800"
                  }`}
                >
                  Sign Up
                </button>
              </div>
            </div>

            <div className="mb-6 flex justify-center">
              {mounted && (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  theme="filled_blue"
                  size="large"
                  shape="pill"
                />
              )}
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <div className="flex items-center gap-4 mb-6">
              <div className="h-px flex-1 bg-slate-700"></div>
              <span className="text-xs text-slate-500 uppercase tracking-[0.2em]">or continue with email</span>
              <div className="h-px flex-1 bg-slate-700"></div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "signUp" && (
                <label className="block text-sm text-slate-300">
                  <span>Name</span>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                  />
                </label>
              )}

              <label className="block text-sm text-slate-300">
                <span>Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              <label className="block text-sm text-slate-300">
                <span>Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  className="mt-2 w-full rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
                />
              </label>

              {mode === "signIn" && (
                <div className="flex items-center justify-between text-sm text-slate-400">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                    />
                    Remember me
                  </label>
                  <button type="button" className="text-cyan-400 hover:text-cyan-200">
                    Forgot?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Loading..." : mode === "signIn" ? "Sign In" : "Create Account"}
              </button>
            </form>
          </>
        ) : (
          <>
            <div className="mb-8 flex flex-col gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400 font-semibold">
                  Verify Email
                </p>
                <h1 className="mt-3 text-3xl font-semibold">Enter OTP Code</h1>
                <p className="mt-2 text-sm text-slate-400 text-balance">
                  We sent a 6-digit verification code to <span className="font-semibold text-white break-all">{verificationEmail}</span>.
                </p>
              </div>
            </div>

            {localError && (
              <div className="mb-4 rounded-3xl border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
                {localError}
              </div>
            )}

            <form onSubmit={handleOtpSubmit} className="space-y-6">
              <label className="block text-sm text-slate-300">
                <span>Verification Code</span>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
                  placeholder="123456"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  className="mt-2 w-full text-center tracking-[0.5em] text-2xl font-bold rounded-3xl border border-slate-800 bg-slate-950 px-4 py-3 text-white outline-none transition focus:border-cyan-500 placeholder-slate-900 placeholder-tracking-[0.1em]"
                />
              </label>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full rounded-3xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {loading ? "Verifying..." : "Verify & Continue"}
              </button>

              <div className="flex flex-col gap-3 text-center text-sm">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={loading}
                  className="text-cyan-400 hover:text-cyan-200 font-semibold cursor-pointer disabled:opacity-50"
                >
                  Resend Verification Code
                </button>
                
                <button
                  type="button"
                  onClick={() => {
                    console.log("Going back to signIn mode");
                    setMode("signIn");
                    setLocalError("");
                  }}
                  className="text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          </>
        )}

        <div className="mt-6 border-t border-slate-800 pt-4 text-center text-sm text-slate-500">
          <p>
            By continuing, you agree to our <span className="text-cyan-400">Terms</span> and <span className="text-cyan-400">Privacy</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
