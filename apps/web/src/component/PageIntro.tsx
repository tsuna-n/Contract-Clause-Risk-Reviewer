import type { ReactNode } from "react";

export default function PageIntro({ eyebrow, title, description, aside }: {
  eyebrow: string; title: string; description: string; aside?: ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {aside && <div className="page-intro-aside">{aside}</div>}
    </div>
  );
}
