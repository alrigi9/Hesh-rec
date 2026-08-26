export type TemplateId =
  | "auto"
  | "executive"
  | "project"
  | "sales"
  | "security"
  | "interview"
  | "lecture"
  | "brainstorm";

export interface TemplateDefinition {
  id: TemplateId;
  label: string;
  labelAr: string;
  badge: string;
  badgeAr: string;
  description: string;
  descriptionAr: string;
  iconName: string;
  promptDirective: string;
}

export const VALID_TEMPLATES: TemplateId[] = [
  "auto",
  "executive",
  "project",
  "sales",
  "security",
  "interview",
  "lecture",
  "brainstorm",
];

export function normalizeTemplate(rawTemplate?: string | null): TemplateId {
  if (!rawTemplate || typeof rawTemplate !== "string") return "auto";
  const cleaned = rawTemplate.trim().toLowerCase();
  if (VALID_TEMPLATES.includes(cleaned as TemplateId)) {
    return cleaned as TemplateId;
  }
  // Mapping legacy synonyms safely
  if (cleaned === "academic" || cleaned === "structured") return "lecture";
  if (cleaned === "ideation" || cleaned === "strategy") return "brainstorm";
  return "auto";
}

export const TEMPLATES_CONFIG: Record<TemplateId, TemplateDefinition> = {
  auto: {
    id: "auto",
    label: "Auto (Inferred)",
    labelAr: "تلقائي (استنتاج ذكي)",
    badge: "Auto",
    badgeAr: "تلقائي",
    description: "Automatically infers meeting dynamics and produces a balanced, full-spectrum executive intelligence breakdown.",
    descriptionAr: "يستنتج طبيعة اللقاء تلقائياً ويقدم تحليلاً متوازناً وشاملاً.",
    iconName: "Sparkles",
    promptDirective: `ANALYSIS OBJECTIVE [AUTO MODE]:
- Detect the natural domain and format of the meeting strictly from what is spoken in the transcript.
- Deliver a factual executive synthesis reflecting only topics, decisions, and deliverables explicitly stated.
- If the transcript is short, simple, or a test, keep the analysis minimal and factual without padding.`,
  },
  executive: {
    id: "executive",
    label: "Executive Brief",
    labelAr: "ملخص قيادي وتوجيهي",
    badge: "Executive",
    badgeAr: "قيادي",
    description: "Focuses on strategic decisions, business implications, risks, priorities, leadership ownership, and deadlines.",
    descriptionAr: "يركز على القرارات الاستراتيجية، الأثر المالي والتشغيلي، والمخاطر والتوجيهات القيادية.",
    iconName: "Briefcase",
    promptDirective: `ANALYSIS OBJECTIVE [EXECUTIVE MODE]:
- Emphasize high-level leadership decisions, business impact, risks, and strategic trade-offs explicitly mentioned in the transcript.
- Keep the narrative concise, factual, and strictly grounded in statements made.
- Do NOT invent executive decisions, strategic trade-offs, ROI metrics, or leadership directives not present in the transcript.`,
  },
  project: {
    id: "project",
    label: "Project & Delivery",
    labelAr: "إدارة المشاريع والتسليم",
    badge: "Project",
    badgeAr: "مشاريع",
    description: "Focuses on delivery milestones, blockers, dependencies, sprint deliverables, owners, and strict deadlines.",
    descriptionAr: "يركز على معالم التسليم، العوائق (Blockers)، المسؤوليات، وخطط العمل الدقيقة.",
    iconName: "Kanban",
    promptDirective: `ANALYSIS OBJECTIVE [PROJECT & DELIVERY MODE]:
- Emphasize operational deliverables, technical dependencies, project milestones, and blockers explicitly discussed in the transcript.
- Extract action items only when clear commitments, owners, or tasks are directly stated.
- Do NOT invent sprint milestones, technical blockers, deadlines, or task owners not explicitly mentioned.`,
  },
  sales: {
    id: "sales",
    label: "Sales & Client",
    labelAr: "مبيعات واجتماعات عملاء",
    badge: "Sales",
    badgeAr: "مبيعات",
    description: "Focuses on customer needs, pain points, objections, buying signals, budget mentions, commitments, and follow-ups.",
    descriptionAr: "يركز على متطلبات العميل، نقاط الألم، الاعتراضات، الميزانيات، وفرص الإغلاق والمتابعة.",
    iconName: "BadgePercent",
    promptDirective: `ANALYSIS OBJECTIVE [SALES & CLIENT DISCOVERY MODE]:
- Emphasize customer requirements, questions, pain points, objections, or commitments explicitly mentioned in the transcript.
- Do NOT invent commercial numbers, budget figures, buying signals, deal stages, next steps, or customer objections not in the transcript.`,
  },
  security: {
    id: "security",
    label: "Security & Compliance",
    labelAr: "الأمن السيبراني والامتثال",
    badge: "Security",
    badgeAr: "أمن سيبراني",
    description: "Focuses on security controls, risks, vulnerabilities, compliance (SOC 2, ISO 27001, NIST), audit evidence, and remediation.",
    descriptionAr: "يركز على الضوابط الأمنية، الثغرات، معايير الامتثال والتدقيق (SOC 2, ISO)، وخطط المعالجة.",
    iconName: "ShieldCheck",
    promptDirective: `ANALYSIS OBJECTIVE [SECURITY & COMPLIANCE MODE]:
- Emphasize security controls, risks, audit policies, or compliance frameworks explicitly mentioned in the transcript.
- Do NOT invent vulnerabilities, compliance failures, security incidents, remediation plans, or audit findings not discussed.`,
  },
  interview: {
    id: "interview",
    label: "Interview & Assessment",
    labelAr: "مقابلات وتقييم مرشحين",
    badge: "Interview",
    badgeAr: "مقابلة",
    description: "Focuses on questions asked, candidate responses, technical competencies, strengths, concerns, and hiring signals.",
    descriptionAr: "يركز على الأسئلة المطروحة، إجابات المرشح، الكفاءات الفنية، ونقاط القوة والملاحظات.",
    iconName: "UserCheck",
    promptDirective: `ANALYSIS OBJECTIVE [INTERVIEW & TALENT EVALUATION MODE]:
- Emphasize interview questions asked, candidate responses, and domain competencies explicitly discussed in the transcript.
- Do NOT invent candidate strengths/weaknesses, hiring recommendations, or evaluation criteria not present in the recording.`,
  },
  lecture: {
    id: "lecture",
    label: "Lecture & Knowledge",
    labelAr: "محاضرات ونقل المعرفة",
    badge: "Lecture",
    badgeAr: "محاضرة",
    description: "Focuses on core concepts, definitions, structured topic hierarchy, key takeaways, examples, and study notes.",
    descriptionAr: "يركز على المفاهيم الجوهرية، التعريفات، الهيكل التعليمي، وأهم الملاحظات الدراسية.",
    iconName: "GraduationCap",
    promptDirective: `ANALYSIS OBJECTIVE [LECTURE & KNOWLEDGE SHARING MODE]:
- Emphasize foundational theories, definitions, concepts, and key takeaways presented in the transcript.
- Do NOT invent academic concepts, definitions, study topics, or assignments not discussed in the session.`,
  },
  brainstorm: {
    id: "brainstorm",
    label: "Brainstorming & Ideation",
    labelAr: "عصف ذهني وابتكار",
    badge: "Brainstorm",
    badgeAr: "عصف ذهني",
    description: "Focuses on proposed ideas, thematic idea clusters, pros/cons, exploratory directions, and potential experiments.",
    descriptionAr: "يركز على الأفكار المقترحة، تصنيف المبادرات، الإيجابيات والسلبيات، ومسارات التجربة.",
    iconName: "Lightbulb",
    promptDirective: `ANALYSIS OBJECTIVE [BRAINSTORMING & IDEATION MODE]:
- Emphasize creative ideas, divergent perspectives, and exploratory avenues explicitly voiced in the session.
- Do NOT invent new brainstormed ideas, pros/cons, or conclusions not proposed by participants.`,
  },
};
