# 🗺️ RecMap — التوثيق المعماري والتقني الشامل للمشروع

هذا الملف يحتوي على الدليل الشامل والمفصل لمنظومة **RecMap** بالكامل: الخدمات السحابية، البنية المعمارية، مسارات الملفات في جهازك، واجهات الـ APIs، وسير البيانات وقواعد الأمان.

---

## 1. ما هو المشروع؟ (Project Overview)
**RecMap** هي منصة ذكاء اصطناعي تفاعلية مصممة لتحويل الاجتماعات والملفات الصوتية إلى:
* ملخص تنفيذي مقسم (Executive Brief).
* مهام وتكليفات مستخرجة (Action Items).
* خريطة ذهنية شجرية بصرية تفاعلية (Interactive Mind Map).
* تفريغ صوتي دقيق مقسم زمنياً (Diarized Transcript).
* مساعد ذكي للاستفسار عن تفاصيل الاجتماع (AI Chat Assistant).
* دعم ثنائي متكامل للغتين العربية والإنجليزية.

---

## 2. المنظومة السحابية والمواقع المستخدمة (Cloud Services & Ecosystem)

| الموقع / المنصة | الرابط المباشر | الدور في المشروع | سبب الاختيار |
| :--- | :--- | :--- | :--- |
| **Vercel** | [https://vercel.com](https://vercel.com) | استضافة الفرونت إند ودوال الـ Serverless API Routes | استجابة سريعة، ربط تلقائي بـ Git، إدارة النطاقات، وشهادات SSL تلقائية. |
| **Supabase** | [https://supabase.com](https://supabase.com) | قاعدة البيانات (Postgres) + التوثيق السحابي + التخزين | إدارة الجلسات (`auth`)، حفظ سجلات الاجتماعات (`sessions`)، واستضافة الملفات في التخزين (`recordings` bucket). |
| **Groq Cloud** | [https://console.groq.com](https://console.groq.com) | محرك استدلال الذكاء الاصطناعي الفائق | تشغيل `whisper-large-v3` للتفريغ بسرعة فائقة، ونموذج `llama-3.3-70b-versatile` للتلخيص واستخراج الخرائط بتكلفة تكاد تنعدم. |
| **Google Cloud Console** | [https://console.cloud.google.com](https://console.cloud.google.com) | إدارة مصادقة Google OAuth 2.0 Client | تفعيل الدخول المباشر بالنافذة المنبثقة الرسمية (Google Identity Services) عبر نطاق `recmap.tech`. |
| **GitHub Developer** | [https://github.com/settings/developers](https://github.com/settings/developers) | تطبيق GitHub OAuth | تمكين تسجيل الدخول بحسابات GitHub البرمجية عبر Supabase. |
| **مزود الدومين** | لوحة تحكم الـ DNS | إدارة دومين `recmap.tech` | توجيه سجلات A / CNAME إلى سيرفرات Vercel. |

---

## 3. المسار المحلي وهيكلة الملفات في جهازك (Project Structure)

### المسار الأساسي في الجهاز:
```text
D:\claude\Hesh rec\frontend
```

### شجرة الملفات البرمجية التفصيلية:
```text
D:\claude\Hesh rec\frontend\
│
├── .env.local / .env.production      <-- مفاتيح الـ APIs وبيانات الاتصال السرية
├── package.json                      <-- مكتبات المشروع (Next.js 14/15, Tailwind, Supabase JS, Lucide)
├── tsconfig.json                     <-- إعدادات TypeScript
│
└── src\
    ├── app\
    │   ├── layout.tsx                <-- القالب الجذري، الخطوط، وتغليف الـ AuthProvider
    │   ├── page.tsx                  <-- لوحة التحكم ومساحة العمل الرئيسية (Workspace)
    │   │
    │   ├── login\
    │   │   └── page.tsx              <-- صفحة تسجيل الدخول وإنشاء الحساب (Google Pop-up + GitHub + Email)
    │   │
    │   ├── share\[id]\
    │   │   └── page.tsx              <-- صفحة المشاركة العامة للعرض فقط بدون تسجيل دخول
    │   │
    │   └── api\                      <-- مسارات الواجهات الخلفية (Next.js Route Handlers)
    │       ├── process-audio\
    │       │   └── route.ts          <-- المحرك الخلفي: استقبال مسار الصوت، التخاطب مع Groq، والحفظ في Supabase
    │       ├── transcribe-direct\
    │       │   └── route.ts          <-- مسار احتياطي لتفريغ الملفات الصوتية الصغيرة
    │       ├── upload-url\
    │       │   └── route.ts          <-- توليد روابط رفع مباشرة إلى Supabase Storage لتجاوز حدود الحجم
    │       └── sessions\
    │           ├── route.ts          <-- استرجاع كافة اجتماعات المستخدم من Supabase
    │           └── [id]\route.ts     <-- جلب / تعديل / حذف اجتماع محدد
    │
    ├── components\                   <-- مكونات الواجهة الرسومية (UI Components)
    │   ├── Sidebar.tsx               <-- القائمة الجانبية لقائمة الاجتماعات مع Drawer للجوال
    │   ├── Header.tsx                <-- الشريط العلوي، الحساب، وحالة الاشتراك
    │   ├── MeetingView.tsx           <-- شاشة عرض الملخص والمهام والتفريغ الصوتي مع شريط التنقل السفلي للجوال
    │   ├── MindmapView.tsx           <-- شاشة الخريطة الذهنية مع أدوات التكبير والتوسيط التلقائي
    │   ├── UploadModal.tsx           <-- نافذة رفع الملفات ودعم صيغ الآيفون والجوال (.m4a)
    │   └── ui\                       <-- أزرار، حقول إدخال، وتنبيهات
    │
    └── lib\ / context\
        ├── AuthContext.tsx           <-- إدارة حالة تسجيل دخول المستخدم ومزامنة الجلسة
        ├── supabaseClient.ts         <-- تهيئة اتصال عميل Supabase للمتصفح
        └── api.ts                    <-- دوال استدعاء الـ APIs والتحكم في المهلة ومعالجة الأخطاء
```

---

## 4. متغيرات البيئة ومفاتيح الـ APIs (Environment Variables)
توضع في ملف `frontend/.env.local` وتُضبط في إعدادات Vercel Settings -> Environment Variables:

```env
# اتصال Supabase (قاعدة البيانات والتوثيق)
NEXT_PUBLIC_SUPABASE_URL=https://bdgjsmwtxfacgqqhwtzw.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# مفتاح Google Identity للنافذة المنبثقة
NEXT_PUBLIC_GOOGLE_CLIENT_ID=xxxxxxxxxxxx-xxxxxxxxxxxxxxxx.apps.googleusercontent.com

# محرك الذكاء الاصطناعي السريع
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# الرابط الأساسي للمنصة
NEXT_PUBLIC_APP_URL=https://recmap.tech
```

---

## 5. دورة حياة رفع ومعالجة البيانات (End-to-End Data Pipeline)

```text
[1. المستخدم يختار ملف صوتي من الجوال أو اللابتوب]
                         │
                         ▼
[2. UploadModal.tsx: رفع الملف مباشرة إلى Supabase Storage Bucket ('recordings')]
                         │
                         ▼ (إرسال { file_url, title, template, language })
[3. POST /api/process-audio على Vercel Serverless]
                         │
                         ├─► استدعاء Groq Whisper API (whisper-large-v3) ──► تفريغ النص (Transcript)
                         │
                         ├─► استدعاء Groq LLaMA 3.3 (70B) / Gemini ──► استخراج الملخص، المهام، وشجرة الخريطة
                         │
                         ▼
[4. كتابة السجل كاملاً في Supabase Database (جدول sessions)]
                         │
                         ▼
[5. المزامنة التلقائية مع الجوال واللابتوب عبر استعلام sessions المرتبط بالـ user_id]
```

---

## 6. هيكل قاعدة البيانات وسياسات الأمان (Supabase Schema & RLS)

### جدول الاجتماعات (`sessions`):
* `id` (UUID - Primary Key)
* `user_id` (UUID - مربوط بـ auth.users.id)
* `title` (Text) — عنوان الاجتماع
* `summary` / `executive_summary` (Text) — الملخص والركائز الأساسية
* `action_items` (JSONB) — قائمة المهام والمسؤولين عنها
* `mindmap_markdown` (Text) — التركيب الهيكلي للخريطة الذهنية
* `transcript` (Text) — التفريغ الصوتي الكامل
* `transcript_segments` (JSONB) — الطوابع الزمنية والمتحدثين
* `strategic_insights` (JSONB) — بيانات وصفية، تصنيفات، وتفاصيل الاجتماع
* `created_at` (Timestamp with Timezone)

### سياسات الأمان (Row Level Security - RLS):
```sql
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert their own sessions"
ON sessions FOR INSERT TO authenticated
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own sessions"
ON sessions FOR SELECT TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own sessions"
ON sessions FOR UPDATE TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own sessions"
ON sessions FOR DELETE TO authenticated
USING (auth.uid() = user_id);
```

---

## 7. تفاصيل واجهات الـ APIs ومواصفاتها (API Endpoints)

### 1. `POST /api/process-audio`
* **المسار:** `src/app/api/process-audio/route.ts`
* **المدخلات (Body JSON):**
```json
{
  "file_url": "https://bdgjsmwtxfacgqqhwtzw.supabase.co/storage/v1/object/public/recordings/audio.m4a",
  "title": "Meeting Title",
  "template": "Executive Summary",
  "language": "auto"
}
```
* **المخرجات (Response 200 OK):** كائن JSON يحتوي على كافة عناصر التحليل ومعرف الجلسة `id`.

### 2. `POST /api/upload-url`
* **المسار:** `src/app/api/upload-url/route.ts`
* **الوظيفة:** توليد رابط رفع موقع (Signed Upload URL) للرفع المباشر إلى Supabase Storage لتفادي قيود الـ 4.5MB على Vercel.

### 3. `GET /api/sessions`
* **المسار:** `src/app/api/sessions/route.ts`
* **الوظيفة:** استرجاع كافة اجتماعات المستخدم المسجل مرتبة تنازلياً حسب التاريخ.

### 4. `GET /api/sessions/[id]`
* **المسار:** `src/app/api/sessions/[id]/route.ts`
* **الوظيفة:** جلب بيانات اجتماع محدد بالكامل لعرضه داخل مساحة العمل أو مشاركته.

---

## 8. أوامر البناء والنشر عبر موجه الأوامر (Terminal Commands)

```bash
# الانتقال إلى مسار الواجهة
cd "D:/claude/Hesh rec/frontend"

# تشغيل بيئة التطوير المحلية
npm run dev

# بناء المشروع واختبار خلوه من الأخطاء
npm run build

# النشر المباشر إلى الإنتاج على النطاق الحي
npx vercel --prod --yes
npx vercel alias set frontend recmap.tech
```
