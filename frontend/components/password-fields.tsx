"use client";
import { useId, useState } from "react";
import { Check, X } from "lucide-react";
import { passwordRules } from "@/lib/password";

export function PasswordFields({ label = "Password" }: { label?: string }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const id = useId();
  return (
    <>
      <label>
        {label}
        <input
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-describedby={id}
        />
      </label>
      <ul id={id} className="password-rules" aria-label="Password requirements">
        {passwordRules.map((rule) => (
          <li key={rule.label} className={rule.test(password) ? "met" : ""}>
            <span aria-hidden="true">{rule.test(password) ? "✓" : "○"}</span>{" "}
            {rule.label}
          </li>
        ))}
      </ul>
      <label>
        Confirm password
        <input
          type="password"
          name="confirm_password"
          aria-label="Confirm password"
          autoComplete="new-password"
          required
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          aria-invalid={!!confirmation && confirmation !== password}
          aria-describedby={`${id}-match`}
        />
        <small
          id={`${id}-match`}
          className={`password-match${confirmation ? (confirmation === password ? " met" : " unmet") : ""}`}
          aria-live="polite"
          aria-atomic="true"
        >
          {confirmation ? (
            confirmation === password ? (
              <>
                <Check size={14} aria-hidden="true" /> Passwords match
              </>
            ) : (
              <>
                <X size={14} aria-hidden="true" /> Passwords do not match
              </>
            )
          ) : (
            "Enter the same password again."
          )}
        </small>
      </label>
    </>
  );
}
