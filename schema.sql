--
-- PostgreSQL database dump
--

\restrict nxIkwgqick04ilwoxSwJ8yehp0eqwfKv76Mq6TuQzCN5JfiqMjcehHfbsCyQeEL

-- Dumped from database version 18.6 (Debian 18.6-3)
-- Dumped by pg_dump version 18.6 (Debian 18.6-3)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_analysis (
    analysis_id bigint NOT NULL,
    report_id bigint NOT NULL,
    detected_language character varying(30),
    detected_category character varying(50),
    confidence_score numeric(5,2),
    analysis_result text,
    analyzed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_analysis_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ai_analysis ALTER COLUMN analysis_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ai_analysis_analysis_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alerts (
    alert_id bigint NOT NULL,
    user_id bigint NOT NULL,
    report_id bigint,
    alert_title character varying(255) NOT NULL,
    alert_message text NOT NULL,
    alert_type character varying(50),
    is_read boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: alerts_alert_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.alerts ALTER COLUMN alert_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.alerts_alert_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: complaint_drafts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaint_drafts (
    draft_id bigint NOT NULL,
    report_id bigint NOT NULL,
    user_id bigint NOT NULL,
    complaint_title character varying(255),
    complaint_content text NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT complaint_drafts_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'reviewed'::character varying, 'submitted'::character varying])::text[])))
);


--
-- Name: complaint_drafts_draft_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.complaint_drafts ALTER COLUMN draft_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.complaint_drafts_draft_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence (
    evidence_id bigint NOT NULL,
    report_id bigint NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_type character varying(50),
    file_size bigint,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    extracted_text text
);


--
-- Name: evidence_evidence_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.evidence ALTER COLUMN evidence_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.evidence_evidence_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: parent_child; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parent_child (
    relationship_id bigint NOT NULL,
    parent_id bigint NOT NULL,
    child_id bigint NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT parent_child_check CHECK ((parent_id <> child_id))
);


--
-- Name: parent_child_relationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.parent_child ALTER COLUMN relationship_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.parent_child_relationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reports (
    report_id bigint NOT NULL,
    user_id bigint NOT NULL,
    report_category character varying(50) NOT NULL,
    description text,
    incident_date date,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT reports_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'under_review'::character varying, 'resolved'::character varying, 'rejected'::character varying])::text[])))
);


--
-- Name: reports_report_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.reports ALTER COLUMN report_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.reports_report_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: suspected_offenders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suspected_offenders (
    offender_id bigint NOT NULL,
    report_id bigint NOT NULL,
    reported_name character varying(150),
    reported_username character varying(150),
    platform character varying(100),
    match_notes text,
    verification_status character varying(30) DEFAULT 'unverified'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT suspected_offenders_verification_status_check CHECK (((verification_status)::text = ANY ((ARRAY['unverified'::character varying, 'under_review'::character varying, 'verified'::character varying, 'dismissed'::character varying])::text[])))
);


--
-- Name: suspected_offenders_offender_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.suspected_offenders ALTER COLUMN offender_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.suspected_offenders_offender_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id bigint NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(150),
    phone character varying(20),
    password_hash text NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'parent'::character varying, 'child'::character varying])::text[])))
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.users ALTER COLUMN user_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_analysis ai_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analysis
    ADD CONSTRAINT ai_analysis_pkey PRIMARY KEY (analysis_id);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (alert_id);


--
-- Name: complaint_drafts complaint_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_drafts
    ADD CONSTRAINT complaint_drafts_pkey PRIMARY KEY (draft_id);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (evidence_id);


--
-- Name: parent_child parent_child_parent_id_child_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_child
    ADD CONSTRAINT parent_child_parent_id_child_id_key UNIQUE (parent_id, child_id);


--
-- Name: parent_child parent_child_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_child
    ADD CONSTRAINT parent_child_pkey PRIMARY KEY (relationship_id);


--
-- Name: reports reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_pkey PRIMARY KEY (report_id);


--
-- Name: suspected_offenders suspected_offenders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suspected_offenders
    ADD CONSTRAINT suspected_offenders_pkey PRIMARY KEY (offender_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: ai_analysis ai_analysis_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analysis
    ADD CONSTRAINT ai_analysis_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(report_id);


--
-- Name: alerts alerts_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(report_id);


--
-- Name: alerts alerts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: complaint_drafts complaint_drafts_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_drafts
    ADD CONSTRAINT complaint_drafts_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(report_id);


--
-- Name: complaint_drafts complaint_drafts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_drafts
    ADD CONSTRAINT complaint_drafts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: evidence evidence_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(report_id);


--
-- Name: parent_child parent_child_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_child
    ADD CONSTRAINT parent_child_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.users(user_id);


--
-- Name: parent_child parent_child_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_child
    ADD CONSTRAINT parent_child_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.users(user_id);


--
-- Name: reports reports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: suspected_offenders suspected_offenders_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suspected_offenders
    ADD CONSTRAINT suspected_offenders_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(report_id);


--
-- PostgreSQL database dump complete
--

\unrestrict nxIkwgqick04ilwoxSwJ8yehp0eqwfKv76Mq6TuQzCN5JfiqMjcehHfbsCyQeEL

