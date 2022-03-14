import React, { useState } from "react";
import { useDispatch } from "react-redux";
import { AppDispatch } from "../../../redux/store";
import { loginUser } from "../../../redux/actions/AuthAction";
import FormInput from "./form-input";
import FormCheckbox from "./form-checkbox";
import SubmitButton from "./submit-button";
import SocialLoginButtons from "./social-login-buttons";

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const dispatch = useDispatch<AppDispatch>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    await dispatch(loginUser({ email, password }));
    setIsLoading(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-center mb-6">
        {/* Logo or illustration can go here if needed */}
      </div>

      <div className="space-y-6">
        <SocialLoginButtons />

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-[#3C5873]"></span>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-[#1F1F1F] text-[#B0BEC5]">or continue with email</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <FormInput
            id="loginEmail"
            label="Email"
            type="email"
            placeholder="john@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor="loginPassword" className="text-sm font-medium text-[#E0E0E0]">
                Password
              </label>
              <a href="#" className="text-sm text-[#00C9A7] hover:text-[#00C9A7]/80 transition-colors">
                Forgot password?
              </a>
            </div>
            <FormInput
              id="loginPassword"
              type="password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <FormCheckbox id="remember" label="Remember me" />

          <SubmitButton
            isLoading={isLoading}
            text="Sign in with Email"
            className="w-full bg-[#1E2A38] hover:bg-[#3C5873] text-[#E0E0E0] py-2.5 rounded-lg transition-all duration-200 border border-[#3C5873] hover:border-[#00C9A7] shadow-lg shadow-[#1E2A38]/10"
          />
        </form>
      </div>
    </div>
  );
}
