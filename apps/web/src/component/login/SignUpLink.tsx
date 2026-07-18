interface SignUpLinkProps {
  onSignUpClick?: () => void;
}

/**
 * SignUpLink — black-theme sign-up prompt with cyan accent link.
 */
export default function SignUpLink({ onSignUpClick }: SignUpLinkProps) {
  return (
    <p className="text-center text-sm text-zinc-500">
      Don't have an account?{" "}
      <button
        onClick={onSignUpClick}
        className="text-cyan-400 hover:text-cyan-300 font-semibold transition-colors duration-150 cursor-pointer"
      >
        Sign up
      </button>
    </p>
  );
}

