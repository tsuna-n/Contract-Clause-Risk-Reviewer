interface SignUpLinkProps {
  onSignUpClick?: () => void;
}

/**
 * SignUpLink — navy-theme sign-up prompt with navy accent link.
 */
export default function SignUpLink({ onSignUpClick }: SignUpLinkProps) {
  return (
    <p className="text-center text-sm text-navy-300">
      Don't have an account?{" "}
      <button
        onClick={onSignUpClick}
        className="text-navy-200 hover:text-navy-100 font-semibold transition-colors duration-150 cursor-pointer"
      >
        Sign up
      </button>
    </p>
  );
}

