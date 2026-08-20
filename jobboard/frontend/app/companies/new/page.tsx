import { redirect } from "next/navigation";

/** Company creation lives on Post a job (single flow). */
export default function CompaniesNewRedirect() {
  redirect("/post-job");
}
