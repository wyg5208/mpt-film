import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { LogPanel } from "../logs/LogRail";
import { VideoPreview } from "./VideoPreview";

type TaskDetailData = {
  task_id: string;
  state: number;
  progress?: number;
  videos?: string[];
  subjects?: string[];
};

export function TaskDetail({ taskId }: { taskId: string }) {
  const { data } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.get<TaskDetailData>(`/tasks/${taskId}`),
    refetchInterval: 5000,
  });
  const videos = data?.videos ?? [];

  return (
    <div className="detail">
      <div className="card">
        <h2>Task {taskId.slice(0, 8)}</h2>
        <p className="muted mono">{taskId}</p>
        <p>
          state: <strong>{data?.state ?? "…"}</strong> · progress: {data?.progress ?? 0}%
        </p>
        {videos.map((v) => (
          <div key={v} className="video-block">
            <VideoPreview path={v} />
            <a className="btn ghost" href={undefined} onClick={(e) => e.preventDefault()}>
              {v}
            </a>
          </div>
        ))}
      </div>
      <LogPanel taskId={taskId} />
    </div>
  );
}
