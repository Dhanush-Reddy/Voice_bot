/**
 * Comprehensive tests for frontend/src/app/dashboard/calls/page.tsx
 *
 * Tests call history page functionality:
 * - Loading states
 * - Error handling
 * - Call list display
 * - Search functionality
 * - Empty states
 * - Date and duration formatting
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import CallHistoryPage from '../page';

// Mock environment variable
process.env.NEXT_PUBLIC_BACKEND_URL = 'http://localhost:8000';

// Mock fetch
global.fetch = jest.fn();

const mockCalls = [
    {
        id: 'call-1',
        agent_id: 'agent-abc-123',
        room_name: 'room-test-1',
        status: 'completed',
        outcome: 'success',
        duration_seconds: 120,
        created_at: '2024-01-15T10:30:00Z',
    },
    {
        id: 'call-2',
        agent_id: 'agent-def-456',
        room_name: 'room-test-2',
        status: 'completed',
        outcome: 'not_interested',
        duration_seconds: 45,
        created_at: '2024-01-15T11:00:00Z',
    },
    {
        id: 'call-3',
        agent_id: 'agent-abc-123',
        room_name: 'room-test-3',
        status: 'failed',
        duration_seconds: 0,
        created_at: '2024-01-15T12:00:00Z',
    },
];

describe('CallHistoryPage', () => {
    beforeEach(() => {
        (global.fetch as jest.Mock).mockClear();
    });

    describe('Loading State', () => {
        it('should display loading skeleton while fetching', () => {
            (global.fetch as jest.Mock).mockImplementation(
                () => new Promise(() => {}) // Never resolves
            );

            render(<CallHistoryPage />);

            // Should show loading skeletons
            const skeletons = screen.getAllByRole('generic', { hidden: true });
            expect(skeletons.length).toBeGreaterThan(0);
        });

        it('should show loading animation', () => {
            (global.fetch as jest.Mock).mockImplementation(
                () => new Promise(() => {})
            );

            const { container } = render(<CallHistoryPage />);

            // Check for animate-pulse class
            const pulseElements = container.querySelectorAll('.animate-pulse');
            expect(pulseElements.length).toBeGreaterThan(0);
        });
    });

    describe('Success State', () => {
        it('should display calls after successful fetch', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            expect(screen.getByText('room-test-2')).toBeInTheDocument();
            expect(screen.getByText('room-test-3')).toBeInTheDocument();
        });

        it('should display agent IDs (truncated)', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText(/agent-abc/)).toBeInTheDocument();
            });

            expect(screen.getByText(/agent-def/)).toBeInTheDocument();
        });

        it('should display call statuses with badges', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('success')).toBeInTheDocument();
            });

            expect(screen.getByText('not_interested')).toBeInTheDocument();
            expect(screen.getByText('failed')).toBeInTheDocument();
        });

        it('should format durations correctly', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('2:00')).toBeInTheDocument(); // 120 seconds
            });

            expect(screen.getByText('0:45')).toBeInTheDocument(); // 45 seconds
            expect(screen.getByText('0:00')).toBeInTheDocument(); // 0 seconds
        });

        it('should fetch from correct API endpoint', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(global.fetch).toHaveBeenCalledWith(
                    'http://localhost:8000/api/calls'
                );
            });
        });
    });

    describe('Error State', () => {
        it('should display error message on fetch failure', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: false,
                status: 500,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(
                    screen.getByText(/Could not load call history/)
                ).toBeInTheDocument();
            });
        });

        it('should display error on network failure', async () => {
            (global.fetch as jest.Mock).mockRejectedValueOnce(
                new Error('Network error')
            );

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(
                    screen.getByText(/Could not load call history/)
                ).toBeInTheDocument();
            });
        });

        it('should not show calls table when error occurs', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: false,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.queryByRole('table')).not.toBeInTheDocument();
            });
        });
    });

    describe('Empty State', () => {
        it('should display empty state when no calls exist', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => [],
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('No calls yet')).toBeInTheDocument();
            });

            expect(
                screen.getByText(/Call logs will appear here/)
            ).toBeInTheDocument();
        });

        it('should display empty state icon', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => [],
            });

            const { container } = render(<CallHistoryPage />);

            await waitFor(() => {
                const svg = container.querySelector('svg');
                expect(svg).toBeInTheDocument();
            });
        });
    });

    describe('Search Functionality', () => {
        it('should filter calls by room name', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );
            await user.type(searchInput, 'room-test-1');

            // Should show only matching call
            expect(screen.getByText('room-test-1')).toBeInTheDocument();
            expect(screen.queryByText('room-test-2')).not.toBeInTheDocument();
            expect(screen.queryByText('room-test-3')).not.toBeInTheDocument();
        });

        it('should filter calls by agent ID', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );
            await user.type(searchInput, 'agent-def');

            // Should show only call-2
            expect(screen.queryByText('room-test-1')).not.toBeInTheDocument();
            expect(screen.getByText('room-test-2')).toBeInTheDocument();
            expect(screen.queryByText('room-test-3')).not.toBeInTheDocument();
        });

        it('should be case-insensitive', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );
            await user.type(searchInput, 'ROOM-TEST-1');

            expect(screen.getByText('room-test-1')).toBeInTheDocument();
        });

        it('should show empty state when no matches found', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );
            await user.type(searchInput, 'nonexistent');

            await waitFor(() => {
                expect(screen.getByText('No calls yet')).toBeInTheDocument();
            });
        });

        it('should clear search results when input is cleared', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('room-test-1')).toBeInTheDocument();
            });

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );

            // Type search
            await user.type(searchInput, 'room-test-1');
            expect(screen.queryByText('room-test-2')).not.toBeInTheDocument();

            // Clear search
            await user.clear(searchInput);

            // All calls should be visible again
            expect(screen.getByText('room-test-1')).toBeInTheDocument();
            expect(screen.getByText('room-test-2')).toBeInTheDocument();
            expect(screen.getByText('room-test-3')).toBeInTheDocument();
        });
    });

    describe('UI Elements', () => {
        it('should display page header', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            expect(screen.getByText('Call History')).toBeInTheDocument();
        });

        it('should display page description', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            expect(
                screen.getByText(/Review past calls, transcripts, and outcomes/)
            ).toBeInTheDocument();
        });

        it('should display search icon', () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const { container } = render(<CallHistoryPage />);

            const searchIcon = container.querySelector('svg');
            expect(searchIcon).toBeInTheDocument();
        });

        it('should display table headers', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('Room')).toBeInTheDocument();
            });

            expect(screen.getByText('Agent')).toBeInTheDocument();
            expect(screen.getByText('Status')).toBeInTheDocument();
            expect(screen.getByText('Duration')).toBeInTheDocument();
            expect(screen.getByText('Date')).toBeInTheDocument();
        });
    });

    describe('Data Formatting', () => {
        it('should format duration with leading zeros', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    duration_seconds: 65, // 1:05
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('1:05')).toBeInTheDocument();
            });
        });

        it('should handle calls without created_at', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    created_at: undefined,
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('—')).toBeInTheDocument();
            });
        });

        it('should show outcome if available, otherwise status', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    outcome: 'success',
                    status: 'completed',
                },
                {
                    ...mockCalls[1],
                    outcome: undefined,
                    status: 'failed',
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('success')).toBeInTheDocument();
            });

            expect(screen.getByText('failed')).toBeInTheDocument();
        });
    });

    describe('Edge Cases', () => {
        it('should handle very long room names', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    room_name: 'a'.repeat(100),
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('a'.repeat(100))).toBeInTheDocument();
            });
        });

        it('should handle zero duration', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    duration_seconds: 0,
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('0:00')).toBeInTheDocument();
            });
        });

        it('should handle very large duration', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    duration_seconds: 3600, // 60 minutes
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                expect(screen.getByText('60:00')).toBeInTheDocument();
            });
        });

        it('should handle missing outcome and status gracefully', async () => {
            const calls = [
                {
                    ...mockCalls[0],
                    outcome: undefined,
                    status: undefined,
                },
            ];

            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => calls,
            });

            const { container } = render(<CallHistoryPage />);

            await waitFor(() => {
                // Should still render without crashing
                expect(container).toBeInTheDocument();
            });
        });
    });

    describe('Accessibility', () => {
        it('should have accessible search input', () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );
            expect(searchInput).toHaveAttribute('type', 'text');
        });

        it('should have proper table structure', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            render(<CallHistoryPage />);

            await waitFor(() => {
                const table = screen.getByRole('table');
                expect(table).toBeInTheDocument();
            });

            // Should have proper table structure
            expect(screen.getByRole('table')).toContainElement(
                screen.getAllByRole('row')[0]
            );
        });
    });

    describe('React Hooks', () => {
        it('should only fetch calls once on mount', async () => {
            (global.fetch as jest.Mock).mockResolvedValue({
                ok: true,
                json: async () => mockCalls,
            });

            const { rerender } = render(<CallHistoryPage />);

            await waitFor(() => {
                expect(global.fetch).toHaveBeenCalledTimes(1);
            });

            // Rerender shouldn't trigger another fetch
            rerender(<CallHistoryPage />);

            expect(global.fetch).toHaveBeenCalledTimes(1);
        });

        it('should update search state on input change', async () => {
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: async () => mockCalls,
            });

            const user = userEvent.setup();
            render(<CallHistoryPage />);

            const searchInput = screen.getByPlaceholderText(
                /Search by room name or agent ID/
            );

            expect(searchInput).toHaveValue('');

            await user.type(searchInput, 'test');

            expect(searchInput).toHaveValue('test');
        });
    });
});