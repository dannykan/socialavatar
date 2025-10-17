'use client';
import { useState } from 'react';

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE as string; // Render URL

  const handleAnalyze = async () => {
    setLoading(true);
    setData(null);
    const res = await fetch(`${API_BASE}/run`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ max_media: 30 }) // 可帶 ig_user_id 覆蓋
    });
    const json = await res.json();
    setData(json);
    setLoading(false);
  };

  return (
    <main className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold">IG MBTI 分析</h1>
      <p className="text-sm text-gray-500 mb-4">
        從 IG Profile + Media 做 AI 人格分析（Demo）
      </p>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="px-4 py-2 rounded bg-black text-white"
      >
        {loading ? '分析中...' : '生成人物卡'}
      </button>

      {data && (
        <section className="mt-6 space-y-4">
          <div className="flex items-center gap-4">
            <img src={data.profile?.profile_picture_url} alt="avatar" className="w-16 h-16 rounded-full"/>
            <div>
              <div className="font-semibold">{data.profile?.username}</div>
              <div className="text-sm text-gray-500">
                粉絲 {data.profile?.followers_count}｜貼文 {data.profile?.media_count}
              </div>
            </div>
          </div>

          <div>
            <h2 className="font-bold">MBTI：{data.analysis?.mbti}</h2>
            <ul className="list-disc pl-5 text-sm">
              {(data.analysis?.rationale || []).map((r:string, i:number) => <li key={i}>{r}</li>)}
            </ul>
            <div className="text-sm mt-2">標籤：{(data.analysis?.tags||[]).join('、')}</div>
          </div>

          <div>
            <h3 className="font-semibold mb-2">近期貼文</h3>
            <div className="grid grid-cols-3 gap-2">
              {(data.medias || []).slice(0,12).map((m:any)=>(
                <a key={m.id} href={m.permalink} target="_blank" rel="noreferrer">
                  <img src={m.media_url} className="w-full h-28 object-cover rounded" />
                </a>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
