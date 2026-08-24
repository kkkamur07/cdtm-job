import Link from "next/link";

export default function NotFound() {
    return (
        <div className="shell py-16">
            <div className="card mx-auto max-w-[34rem] p-6">
                <h1 className="text-lg font-semibold">Nothing at this address</h1>
                <p className="mt-2 text-[13.5px] text-muted">
                    The listing may have been closed, or the link may be out of date.
                </p>
                <Link href="/" className="btn mt-4">
                    Back to the feed
                </Link>
            </div>
        </div>
    );
}
