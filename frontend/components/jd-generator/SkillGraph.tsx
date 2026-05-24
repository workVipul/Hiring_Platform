import type { GeneratedJD } from "@/types/jd";

function contentFrequency(jd: GeneratedJD, skill: string): number {
  const text = JSON.stringify(jd).toLowerCase();
  const escaped = skill.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return (text.match(new RegExp(escaped, "g")) ?? []).length;
}

function explicitWeight(jd: GeneratedJD, skill: string): number | null {
  const weights = jd.metadata?.skill_weights;
  if (weights && typeof weights === "object" && !Array.isArray(weights)) {
    const value = (weights as Record<string, unknown>)[skill];
    if (typeof value === "number") {
      const normalized = value <= 10 ? value * 10 : value;
      return Math.max(35, Math.min(100, normalized));
    }
  }
  return null;
}

type SkillLevel = "Core" | "Important" | "Supporting";

type SkillDisplay = {
  name: string;
  level: SkillLevel;
  weight: number;
};

function skillWeight(jd: GeneratedJD, skill: string, maxFrequency: number, index: number): number {
  const normalizedSkill = skill.toLowerCase();
  const title = jd.title.toLowerCase();
  const requirements = (jd.requirements ?? []).join(" ").toLowerCase();
  const summary = (jd.summary ?? "").toLowerCase();
  const corpus = `${title} ${requirements} ${summary}`;

  let inferred = Math.max(46, 66 - index * 3);

  if (index === 0) inferred = Math.max(inferred, 92);
  if (title.includes(normalizedSkill)) inferred = Math.max(inferred, 94);
  if (requirements.includes(normalizedSkill)) inferred = Math.max(inferred, 84);
  if (summary.includes(normalizedSkill)) inferred = Math.max(inferred, 74);
  if (isPrimaryLanguage(normalizedSkill)) inferred = Math.max(inferred, index <= 1 ? 92 : 78);
  if (isCloudOrDevOps(normalizedSkill) && relatedTermAppears(normalizedSkill, corpus)) inferred = Math.max(inferred, 82);
  if (isArchitectureSkill(normalizedSkill) && relatedTermAppears(normalizedSkill, corpus)) inferred = Math.max(inferred, 76);

  const frequency = contentFrequency(jd, skill);
  if (maxFrequency > 0 && frequency > 0) {
    inferred = Math.max(inferred, Math.max(52, Math.round((frequency / maxFrequency) * 72)));
  }

  const weighted = explicitWeight(jd, skill);
  return Math.max(inferred, weighted ?? 0);
}

function skillLevel(weight: number): SkillLevel {
  if (weight >= 86) return "Core";
  if (weight >= 68) return "Important";
  return "Supporting";
}

export default function SkillGraph({ jd }: { jd: GeneratedJD }) {
  const skills = Array.from(new Set((jd.skills ?? []).filter(isTechnicalSkill))).slice(0, 8);
  const frequencies = skills.map((skill) => contentFrequency(jd, skill));
  const maxFrequency = Math.max(...frequencies, 0);
  const skillDisplay = skills
    .map((skill, index): SkillDisplay => {
      const weight = skillWeight(jd, skill, maxFrequency, index);
      return { name: skill, weight, level: skillLevel(weight) };
    })
    .sort((a, b) => b.weight - a.weight);

  if (skills.length === 0) return null;

  return (
    <div className="skill-graph">
      <div className="skill-graph-heading">
        <h3>Skill Graph</h3>
        <span>Required level</span>
      </div>
      {skillDisplay.map((skill) => {
        return (
        <div className={`skill-row ${skill.level.toLowerCase()}`} key={skill.name}>
          <div className="skill-row-meta">
            <span>{skill.name}</span>
            <em>{skill.level}</em>
          </div>
          <div className="skill-track">
            <div className="skill-bar" style={{ width: `${skill.weight}%` }} />
          </div>
        </div>
        );
      })}
    </div>
  );
}

function isPrimaryLanguage(skill: string): boolean {
  return ["python", "java", "golang", "go", "javascript", "typescript", "c#", "c++"].includes(skill);
}

function isCloudOrDevOps(skill: string): boolean {
  return ["cloud", "cloud computing", "amazon aws", "aws", "azure", "gcp", "devops", "jenkins", "docker", "kubernetes"].includes(skill);
}

function isArchitectureSkill(skill: string): boolean {
  return ["microservices", "redis", "database management", "security", "testing", "version control"].includes(skill);
}

function relatedTermAppears(skill: string, text: string): boolean {
  const aliases: Record<string, string[]> = {
    "cloud computing": ["cloud", "aws", "azure", "gcp"],
    "amazon aws": ["aws", "amazon aws", "cloud"],
    "devops": ["devops", "ci/cd", "jenkins"],
    "jenkins": ["jenkins", "ci/cd", "devops"],
    "docker": ["docker", "container"],
    "kubernetes": ["kubernetes", "container", "orchestration"],
    "microservices": ["microservice", "microservices"],
    "database management": ["database", "sql", "nosql", "redis"],
  };
  return (aliases[skill] ?? [skill]).some((alias) => text.includes(alias));
}

function isTechnicalSkill(skill: string): boolean {
  const value = skill.trim().toLowerCase();
  if (!value || value.length > 40) return false;
  const blocked = ["excellent", "communication", "collaboration", "leadership", "problem", "team management", "hybrid", "agile methodology"];
  if (blocked.some((term) => value.includes(term))) return false;
  return true;
}
