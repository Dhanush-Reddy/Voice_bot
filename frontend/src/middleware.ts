import { withAuth } from "next-auth/middleware";

// This protects all routes that match the `matcher` config below
export default withAuth({
    pages: {
        signIn: "/login",
    },
});

export const config = {
    // Protect the dashboard and any subroutes under it
    matcher: ["/dashboard/:path*"],
};
