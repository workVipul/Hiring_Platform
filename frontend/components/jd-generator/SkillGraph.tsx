import type { GeneratedJD } from "@/types/jd";

function contentFrequency(jd: GeneratedJD, skill: string): number {
  const text = JSON.stringify(jd).toLowerCase();
  const escaped = skill.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return (text.match(new RegExp(escaped, "g")) ?? []).length;
}

function skillWeight(jd: GeneratedJD, skill: string, maxFrequency: number): number {
  const weights = jd.metadata?.skill_weights;
  if (weights && typeof weights === "object" && !Array.isArray(weights)) {
    const value = (weights as Record<string, unknown>)[skill];
    if (typeof value === "number") return Math.max(5, Math.min(100, value));
  }

  const frequency = contentFrequency(jd, skill);
  if (maxFrequency <= 0) return 0;
  return Math.max(12, Math.round((frequency / maxFrequency) * 100));
}

export default function SkillGraph({ jd }: { jd: GeneratedJD }) {
  const skills = Array.from(new Set((jd.skills ?? []).filter(isTechnicalSkill))).slice(0, 8);
  const frequencies = skills.map((skill) => contentFrequency(jd, skill));
  const maxFrequency = Math.max(...frequencies, 0);

  if (skills.length === 0) return null;

  return (
    <div className="skill-graph">
      <h3>Skill Graph</h3>
      {skills.map((skill) => (
        <div className="skill-row" key={skill}>
          <span>{skill}</span>
          <div className="skill-track">
            <div className="skill-bar" style={{ width: `${skillWeight(jd, skill, maxFrequency)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function isTechnicalSkill(skill: string): boolean {
  const value = skill.trim().toLowerCase();
  if (!value || value.length > 40) return false;
  const blocked = ["excellent", "communication", "collaboration", "leadership", "problem", "team management", "hybrid", "agile methodology"];
  if (blocked.some((term) => value.includes(term))) return false;
  return true;
}
