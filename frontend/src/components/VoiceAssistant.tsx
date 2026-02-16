"use client";

import { useCallback, useEffect, useState } from "react";
import {
    LiveKitRoom,
    useRoomContext,
    useParticipants,
    useConnectionState,
    RoomAudioRenderer,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { ConnectionState, RoomEvent, Participant, Track } from "livekit-client";

interface VoiceAssistantProps {
    token: string;
    url: string;
    onDisconnect: () => void;
}

export default function VoiceAssistant({
    token,
    url,
    onDisconnect,
}: VoiceAssistantProps) {
    return (
        <LiveKitRoom
            serverUrl={url}
            token={token}
            connect={true}
            audio={true}
            video={false}
            onDisconnected={onDisconnect}
            className="flex flex-col items-center gap-8"
        >
            <ActiveRoom onDisconnect={onDisconnect} />
        </LiveKitRoom>
    );
}

function ActiveRoom({ onDisconnect }: { onDisconnect: () => void }) {
    const room = useRoomContext();
    const connectionState = useConnectionState();
    const participants = useParticipants();
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [statusText, setStatusText] = useState("Connecting…");

    // Track bot speaking state
    useEffect(() => {
        if (!room) return;

        // Handle active speakers
        const handleActiveSpeakers = () => {
            const activeSpeakers = room.activeSpeakers;
            const botSpeaking = activeSpeakers.some(
                (p: Participant) => p.identity !== room.localParticipant.identity
            );
            setIsSpeaking(botSpeaking);
        };

        room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);
        
        return () => {
            room.off(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);
        };
    }, [room]);

    // Update status text
    useEffect(() => {
        switch (connectionState) {
            case ConnectionState.Connecting:
                setStatusText("Connecting…");
                break;
            case ConnectionState.Connected:
                const botParticipant = participants.find(
                    (p: Participant) => p.identity !== room?.localParticipant?.identity
                );
                if (botParticipant) {
                    setStatusText(
                        isSpeaking ? "AI is speaking…" : "Listening to you…"
                    );
                } else {
                    setStatusText("Waiting for AI to join…");
                }
                break;
            case ConnectionState.Reconnecting:
                setStatusText("Reconnecting…");
                break;
            case ConnectionState.Disconnected:
                setStatusText("Disconnected");
                break;
        }
    }, [connectionState, participants, isSpeaking, room]);

    const handleDisconnect = useCallback(() => {
        room?.disconnect();
        onDisconnect();
    }, [room, onDisconnect]);

    // Enable audio on user interaction (required by browser autoplay policy)
    const enableAudio = useCallback(() => {
        if (room) {
            room.startAudio();
            console.log('[Audio] Audio enabled by user interaction');
        }
    }, [room]);

    return (
        <div 
            className="glass-card p-12 flex flex-col items-center gap-8 max-w-md w-full text-center"
            onClick={enableAudio}
        >
            {/* Room audio renderer for all remote audio */}
            <RoomAudioRenderer />
            
            {/* Click to enable audio hint */}
            <p className="text-xs text-slate-500">Click anywhere to enable audio</p>
            
            {/* AI Orb Visualizer */}
            <div className="relative flex items-center justify-center">
                <div className={`ai-orb ${isSpeaking ? "speaking" : "idle"}`} />

                {/* Outer ripple rings when speaking */}
                {isSpeaking && (
                    <>
                        <div
                            className="absolute inset-0 rounded-full border-2 border-primary-400/30 animate-ping"
                            style={{
                                width: "160px",
                                height: "160px",
                                top: "-20px",
                                left: "-20px",
                            }}
                        />
                    </>
                )}
            </div>

            {/* Status */}
            <div className="space-y-2">
                <h2 className="text-xl font-semibold text-slate-200">{statusText}</h2>
                <div className="flex items-center justify-center gap-2">
                    <span className="status-dot connected" />
                    <span className="text-xs text-slate-400 uppercase tracking-wider">
                        Connected
                    </span>
                </div>
            </div>

            {/* Audio level hint */}
            <div className="flex items-center gap-1">
                {[...Array(5)].map((_, i) => (
                    <div
                        key={i}
                        className={`w-1 rounded-full transition-all duration-150 ${isSpeaking
                            ? "bg-primary-400"
                            : "bg-slate-700"
                            }`}
                        style={{
                            height: isSpeaking
                                ? `${12 + Math.random() * 20}px`
                                : "8px",
                            animationDelay: `${i * 100}ms`,
                        }}
                    />
                ))}
            </div>

            {/* Disconnect button */}
            <button
                id="disconnect-button"
                className="btn-connect btn-disconnect"
                onClick={handleDisconnect}
            >
                Disconnect
            </button>
        </div>
    );
}
