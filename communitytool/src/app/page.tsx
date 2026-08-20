import Gate from "@/components/Gate";

export default function Page() {
    return (
        <Gate
            header={
                /* Brand lockup. Scrolls away; the filter toolbar below is what sticks.
                   Plain <img> rather than next/image — the source is an SVG, and this
                   build runs `output: "export"` with image optimisation off. */
                <header className="shell py-5">
                    <a className="group flex w-fit items-center" href="/home">
                        <div className="relative overflow-visible">
                            <img
                                src="/assets/cdtm.svg"
                                alt="CDTM Logo"
                                width={36}
                                height={36}
                                className="h-9 w-auto transition-all duration-500 ease-in-out group-hover:-translate-y-1 group-hover:scale-110 group-hover:rotate-6"
                            />
                        </div>
                        <div className="ml-3 flex items-center">
                            <div className="mr-2 h-6 w-px bg-black" />
                            <span className="text-lg font-semibold" style={{ color: "#134391" }}>
                Community
              </span>
                        </div>
                    </a>
                </header>
            }
        />
    );
}